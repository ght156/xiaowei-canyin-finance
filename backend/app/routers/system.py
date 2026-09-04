"""系统管理（仅管理员）：用户管理、审计日志、备份、CSV 导出。"""
import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import DB_PATH
from ..database import get_db
from ..models import AuditLog, BackupRecord, Transaction, User
from ..schemas import TransactionOut, UserCreate, UserOut, UserUpdate
from ..security import hash_password, require_admin
from ..services.audit import log_action
from ..services.backup import create_backup, restore_backup
from ..utils import PAYMENT_LABELS, TYPE_LABELS, cents_to_yuan

router = APIRouter(tags=["system"])


# ---------------- 用户管理 ----------------
@router.get("/api/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.post("/api/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    username = body.username.strip()
    exists = db.scalar(select(User.id).where(User.username == username))
    if exists:
        raise HTTPException(400, "用户名已存在")
    user = User(username=username, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.flush()
    log_action(db, admin.id, "create", "user", user.id, after={"username": username, "role": body.role})
    db.commit()
    db.refresh(user)
    return user


@router.put("/api/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "用户不存在")
    before = {"role": user.role, "status": user.status}
    if user.id == admin.id and body.status == "disabled":
        raise HTTPException(400, "不能停用自己的账号")
    if body.password is not None:
        user.password_hash = hash_password(body.password)
    if body.role is not None:
        user.role = body.role
    if body.status is not None:
        user.status = body.status
    log_action(
        db, admin.id, "update", "user", user.id, before=before,
        after={"role": user.role, "status": user.status, "password_changed": body.password is not None},
    )
    db.commit()
    db.refresh(user)
    return user


# ---------------- 审计日志 ----------------
@router.get("/api/audit-logs")
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    entity_type: str | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    q = select(AuditLog)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    items = db.scalars(
        q.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    users = {u.id: u.username for u in db.scalars(select(User)).all()}
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": a.id,
                "user_id": a.user_id,
                "username": users.get(a.user_id, "?"),
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "before_data": a.before_data,
                "after_data": a.after_data,
                "created_at": a.created_at,
            }
            for a in items
        ],
    }


# ---------------- 备份 ----------------
@router.get("/api/backups")
def list_backups(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    records = db.scalars(select(BackupRecord).order_by(BackupRecord.id.desc())).all()
    return [
        {
            "id": r.id,
            "file_name": r.file_name,
            "backup_type": r.backup_type,
            "status": r.status,
            "created_at": r.created_at,
        }
        for r in records
    ]


@router.post("/api/backups", status_code=201)
def create_backup_now(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    record = create_backup(db, backup_type="manual")
    log_action(db, admin.id, "backup", "backup_record", record.id, after={"file_name": record.file_name})
    db.commit()
    return {"id": record.id, "file_name": record.file_name, "message": "备份完成"}


@router.post("/api/backups/{file_name}/restore")
def restore_from_backup(file_name: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    try:
        restore_backup(db, file_name)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(400, str(e))
    log_action(db, admin.id, "restore_backup", "backup_record", None, after={"file_name": file_name})
    db.commit()
    return {"ok": True, "message": "恢复完成，请重启服务后刷新页面"}


# ---------------- 数据导出 ----------------
@router.get("/api/export")
def export_csv(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    shop_id: int | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        s = datetime.strptime(start, "%Y-%m-%d").date()
        e = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(422, "日期格式应为 YYYY-MM-DD")
    if s > e:
        raise HTTPException(422, "开始日期不能晚于结束日期")

    q = (
        select(Transaction)
        .where(
            Transaction.deleted_at.is_(None),
            Transaction.biz_date >= s,
            Transaction.biz_date <= e,
        )
        .order_by(Transaction.biz_date, Transaction.id)
    )
    if shop_id is not None:
        q = q.where(Transaction.shop_id == shop_id)
    rows = db.scalars(q).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["日期", "店铺", "类型", "分类", "金额(元)", "支付方式", "备注", "创建人", "创建时间"])
    for tx in rows:
        writer.writerow(
            [
                tx.biz_date.isoformat(),
                tx.shop.name,
                TYPE_LABELS.get(tx.type, tx.type),
                tx.category.name,
                cents_to_yuan(tx.amount_cents),
                PAYMENT_LABELS.get(tx.payment_method, tx.payment_method),
                tx.remark or "",
                tx.creator.username,
                tx.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # BOM 头保证 Excel 直接打开中文不乱码
    content = "\ufeff" + buf.getvalue()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=export_{ts}.csv",
            "X-Row-Count": str(len(rows)),
            "X-Db-Path": str(DB_PATH.name),
        },
    )
