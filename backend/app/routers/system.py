"""系统管理（仅管理员）：用户管理、审计日志、备份、CSV 导出。"""
import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import BACKUP_DIR, DB_PATH
from ..database import get_db
from ..models import AuditLog, BackupRecord, Shop, Transaction, User, UserShop
from ..schemas import TransactionOut, UserCreate, UserOut, UserShopsUpdate, UserUpdate
from ..security import get_current_user, hash_password, require_admin
from ..services.audit import log_action
from ..services.backup import create_backup, restore_backup
from ..tz import naive_now
from ..utils import PAYMENT_LABELS, TYPE_LABELS, cents_to_yuan

router = APIRouter(tags=["system"])


def _set_user_shops(db: Session, user: User, shop_ids: list[int], admin: User) -> None:
    """全量替换用户的店铺授权；记录前后店铺名列表。admin 用户不接受分配。"""
    if user.role == "admin":
        raise HTTPException(400, "管理员默认拥有全部店铺权限，无需分配")
    valid = db.scalars(
        select(Shop).where(Shop.id.in_(shop_ids), Shop.deleted_at.is_(None))
    ).all() if shop_ids else []
    found = {s.id for s in valid}
    invalid = set(shop_ids) - found
    if invalid:
        raise HTTPException(400, f"店铺不存在：{sorted(invalid)}")

    before = [link.shop.name for link in sorted(user.shop_links, key=lambda l: l.shop_id)]
    # 先物理删除旧绑定再插入，避免同事务内 insert 先于 delete 触发 UNIQUE 冲突
    db.query(UserShop).filter(UserShop.user_id == user.id).delete(synchronize_session=False)
    db.flush()
    for sid in sorted(found):
        db.add(UserShop(user_id=user.id, shop_id=sid))
    db.flush()
    # after 直接由查询到的店铺行生成（ORM 关系此时仍是过期缓存，不能读它）
    after = [s.name for s in sorted(valid, key=lambda x: x.id)]
    log_action(db, admin.id, "update_shops", "user", user.id,
               before={"shops": before}, after={"shops": after})


def _bind_all_active_shops(db: Session, user: User) -> None:
    """角色降为 owner/employee 且没有任何授权时，默认绑定全部未删除店铺，避免账号被锁死。"""
    if user.shop_links:
        return
    for shop in db.scalars(select(Shop).where(Shop.deleted_at.is_(None))).all():
        db.add(UserShop(user_id=user.id, shop_id=shop.id))


# ---------------- 用户管理 ----------------
@router.get("/api/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    # 已删除的用户不再出现在列表中，其历史流水与审计记录中的名字保留
    return db.scalars(
        select(User).where(User.deleted_at.is_(None)).order_by(User.id)
    ).all()


@router.post("/api/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    username = body.username.strip()
    existing = db.scalar(select(User).where(User.username == username))
    if existing and existing.deleted_at is None:
        raise HTTPException(400, "用户名已存在")
    if existing:
        # 同名用户曾被删除：恢复账号（用新密码、新角色）
        existing.deleted_at = None
        existing.status = "active"
        existing.role = body.role
        existing.password_hash = hash_password(body.password)
        log_action(db, admin.id, "restore", "user", existing.id,
                   after={"username": username, "role": body.role})
        db.commit()
        db.refresh(existing)
        return existing

    user = User(username=username, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.flush()
    if user.role != "admin" and body.shop_ids:
        _set_user_shops(db, user, body.shop_ids, admin)
    elif user.role in ("owner", "employee"):
        _bind_all_active_shops(db, user)
    log_action(db, admin.id, "create", "user", user.id, after={"username": username, "role": body.role})
    db.commit()
    db.refresh(user)
    return user


@router.put("/api/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(404, "用户不存在")
    before = {"role": user.role, "status": user.status}
    if user.id == admin.id and body.status == "disabled":
        raise HTTPException(400, "不能停用自己的账号")

    # 保护系统最后一个启用中的管理员：任何使其失去 active admin 身份的变更
    # （改成 owner、改成 employee、停用）都必须先确认还有其他 active admin
    if user.role == "admin" and user.status == "active":
        loses_admin = (body.role is not None and body.role != "admin") or (body.status == "disabled")
        if loses_admin:
            others = db.scalar(
                select(func.count(User.id)).where(
                    User.role == "admin",
                    User.status == "active",
                    User.id != user.id,
                )
            )
            if not others:
                raise HTTPException(400, "系统至少需要保留一个启用的管理员账号。")

    if body.password is not None:
        user.password_hash = hash_password(body.password)
    role_before = user.role
    if body.role is not None:
        user.role = body.role
    if body.status is not None:
        user.status = body.status
    # 角色变化时同步店铺授权：升为 admin 清空绑定（默认全部）；降为 owner/employee 且无绑定时绑定全部
    if body.role is not None and body.role != role_before:
        if body.role == "admin":
            user.shop_links.clear()
        else:
            _bind_all_active_shops(db, user)
    log_action(
        db, admin.id, "update", "user", user.id, before=before,
        after={"role": user.role, "status": user.status, "password_changed": body.password is not None},
    )
    db.commit()
    db.refresh(user)
    return user


@router.get("/api/users/{user_id}/shops")
def get_user_shops(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(404, "用户不存在")
    if user.role == "admin":
        return {"shop_ids": [], "all": True}
    return {"shop_ids": [link.shop_id for link in sorted(user.shop_links, key=lambda l: l.shop_id)], "all": False}


@router.put("/api/users/{user_id}/shops")
def update_user_shops(
    user_id: int,
    body: UserShopsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(404, "用户不存在")
    _set_user_shops(db, user, body.shop_ids, admin)
    db.commit()
    db.refresh(user)
    return {"ok": True, "shop_ids": [link.shop_id for link in sorted(user.shop_links, key=lambda l: l.shop_id)]}


@router.delete("/api/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """软删除用户：账号从列表与登录中移除，其历史流水与审计记录中的名字保留。"""
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(404, "用户不存在")
    if user.id == admin.id:
        raise HTTPException(400, "不能删除自己的账号")

    # 删除管理员前确认系统仍有其他启用中的管理员
    if user.role == "admin" and user.status == "active":
        others = db.scalar(
            select(func.count(User.id)).where(
                User.role == "admin", User.status == "active", User.id != user.id
            )
        )
        if not others:
            raise HTTPException(400, "系统至少需要保留一个启用的管理员账号。")

    before = {"username": user.username, "role": user.role, "status": user.status}
    user.deleted_at = naive_now()
    user.status = "disabled"
    log_action(db, admin.id, "delete", "user", user.id, before=before)
    db.commit()
    return {"ok": True, "message": "用户已删除，其历史流水与审计记录仍保留"}


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
def _require_backup_creator(user: User = Depends(get_current_user)) -> User:
    """手动备份：admin/owner 可用，employee 无权。"""
    if user.role == "employee":
        raise HTTPException(403, "员工账号无权创建备份")
    return user


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
def create_backup_now(db: Session = Depends(get_db), user: User = Depends(_require_backup_creator)):
    record = create_backup(db, backup_type="manual")
    log_action(db, user.id, "backup", "backup_record", record.id, after={"file_name": record.file_name})
    db.commit()
    return {"id": record.id, "file_name": record.file_name, "message": "备份完成"}


@router.post("/api/backups/{file_name}/restore")
def restore_from_backup(file_name: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """恢复备份：内部会先创建恢复前安全备份，失败自动回滚。"""
    try:
        restore_backup(db, file_name)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(400, str(e))
    log_action(db, admin.id, "restore_backup", "backup_record", None, after={"file_name": file_name})
    db.commit()
    return {"ok": True, "message": "恢复完成，系统已切回备份时间点的数据"}


@router.get("/api/backups/{file_name}/download")
def download_backup(file_name: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """下载备份文件到本机/手机，用于异地保存。"""
    if "/" in file_name or "\\" in file_name or ".." in file_name:
        raise HTTPException(400, "非法文件名")
    path = BACKUP_DIR / file_name
    if not path.exists():
        raise HTTPException(404, "备份文件不存在")
    return FileResponse(str(path), filename=file_name, media_type="application/octet-stream")


# ---------------- 数据导出 ----------------
@router.get("/api/export")
def export_csv(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    shop_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """导出流水 CSV。admin 全部；owner 仅授权店铺；employee 无权。"""
    if user.role == "employee":
        raise HTTPException(403, "员工账号无权导出数据")
    try:
        s = datetime.strptime(start, "%Y-%m-%d").date()
        e = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(422, "日期格式应为 YYYY-MM-DD")
    if s > e:
        raise HTTPException(422, "开始日期不能晚于结束日期")
    if shop_id is not None:
        from ..permissions import ensure_shop_access

        ensure_shop_access(db, user, shop_id)

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
    else:
        from ..permissions import shop_ids_or_all

        allowed = shop_ids_or_all(db, user)
        if allowed is not None:
            q = q.where(Transaction.shop_id.in_(allowed) if allowed else Transaction.shop_id == -1)
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

    ts = naive_now().strftime("%Y%m%d_%H%M%S")
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
