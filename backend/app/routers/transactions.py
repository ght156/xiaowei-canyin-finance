"""收支流水：新增（所有用户）、查询、管理员编辑/软删除/恢复，全部写审计。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Shop, Transaction, User
from ..schemas import (
    PagedTransactions,
    TransactionCreate,
    TransactionOut,
    TransactionUpdate,
)
from ..security import get_current_user, require_admin
from ..services.audit import log_action
from ..utils import AmountError, cents_to_yuan, parse_amount_to_cents

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def serialize_tx(tx: Transaction) -> dict:
    return {
        "id": tx.id,
        "shop_id": tx.shop_id,
        "shop_name": tx.shop.name,
        "type": tx.type,
        "category_id": tx.category_id,
        "category_name": tx.category.name,
        "amount": cents_to_yuan(tx.amount_cents),
        "payment_method": tx.payment_method,
        "biz_date": tx.biz_date,
        "remark": tx.remark,
        "created_by": tx.created_by,
        "created_by_name": tx.creator.username,
        "created_at": tx.created_at,
        "updated_at": tx.updated_at,
        "deleted_at": tx.deleted_at,
    }


def _validate_refs(db: Session, shop_id: int, tx_type: str, category_id: int) -> None:
    shop = db.get(Shop, shop_id)
    if shop is None:
        raise HTTPException(400, "店铺不存在")
    if shop.status != "active":
        raise HTTPException(400, "店铺已停用")
    cat = db.get(Category, category_id)
    if cat is None:
        raise HTTPException(400, "分类不存在")
    if cat.type != tx_type:
        raise HTTPException(400, "分类类型与收支类型不匹配")
    if cat.status != "active":
        raise HTTPException(400, "分类已停用")


def _parse_amount_or_422(amount: str) -> int:
    try:
        return parse_amount_to_cents(amount)
    except AmountError as e:
        raise HTTPException(422, str(e))


def _get_live_tx(db: Session, tx_id: int) -> Transaction:
    tx = db.get(Transaction, tx_id)
    if tx is None or tx.deleted_at is not None:
        raise HTTPException(404, "流水不存在")
    return tx


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(
    body: TransactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cents = _parse_amount_or_422(body.amount)
    _validate_refs(db, body.shop_id, body.type, body.category_id)

    tx = Transaction(
        shop_id=body.shop_id,
        type=body.type,
        category_id=body.category_id,
        amount_cents=cents,
        payment_method=body.payment_method,
        biz_date=body.biz_date,
        remark=(body.remark or "").strip() or None,
        created_by=user.id,
    )
    db.add(tx)
    db.flush()
    log_action(db, user.id, "create", "transaction", tx.id, after=serialize_tx(tx))
    db.commit()
    db.refresh(tx)
    return serialize_tx(tx)


@router.get("", response_model=PagedTransactions)
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    shop_id: int | None = None,
    type: str | None = None,
    category_id: int | None = None,
    start_date=None,
    end_date=None,
    keyword: str | None = None,
    include_deleted: str = "false",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Transaction)
    show_deleted = include_deleted in ("1", "true")
    if show_deleted:
        if user.role != "admin":
            raise HTTPException(403, "仅管理员可查看回收站")
    else:
        q = q.where(Transaction.deleted_at.is_(None))

    if shop_id is not None:
        q = q.where(Transaction.shop_id == shop_id)
    if type in ("income", "expense"):
        q = q.where(Transaction.type == type)
    if category_id is not None:
        q = q.where(Transaction.category_id == category_id)
    if start_date:
        q = q.where(Transaction.biz_date >= _to_date(start_date))
    if end_date:
        q = q.where(Transaction.biz_date <= _to_date(end_date))
    if keyword:
        q = q.where(Transaction.remark.like(f"%{keyword.strip()}%"))

    total = db.scalar(select(func.count()).select_from(q.subquery()))
    items = db.scalars(
        q.order_by(Transaction.biz_date.desc(), Transaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PagedTransactions(
        total=total,
        page=page,
        page_size=page_size,
        items=[serialize_tx(tx) for tx in items],
    )


def _to_date(value):
    from datetime import date as _date

    if isinstance(value, _date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


@router.get("/{tx_id}", response_model=TransactionOut)
def get_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tx = db.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(404, "流水不存在")
    if tx.deleted_at is not None and user.role != "admin":
        raise HTTPException(404, "流水不存在")
    return serialize_tx(tx)


@router.put("/{tx_id}", response_model=TransactionOut)
def update_transaction(
    tx_id: int,
    body: TransactionUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    tx = _get_live_tx(db, tx_id)
    before = serialize_tx(tx)

    if body.category_id is not None:
        cat = db.get(Category, body.category_id)
        if cat is None or cat.type != tx.type:
            raise HTTPException(400, "分类不存在或类型不匹配")
        tx.category_id = body.category_id
    if body.amount is not None:
        tx.amount_cents = _parse_amount_or_422(body.amount)
    if body.payment_method is not None:
        tx.payment_method = body.payment_method
    if body.biz_date is not None:
        tx.biz_date = body.biz_date
    if body.remark is not None:
        tx.remark = body.remark.strip() or None

    log_action(db, admin.id, "update", "transaction", tx.id, before=before, after=serialize_tx(tx))
    db.commit()
    db.refresh(tx)
    return serialize_tx(tx)


@router.delete("/{tx_id}")
def delete_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """软删除：仅标记 deleted_at，可在回收站恢复。"""
    tx = _get_live_tx(db, tx_id)
    before = serialize_tx(tx)
    tx.deleted_at = datetime.now()
    log_action(db, admin.id, "soft_delete", "transaction", tx.id, before=before)
    db.commit()
    return {"ok": True, "message": "已移入回收站"}


@router.post("/{tx_id}/restore", response_model=TransactionOut)
def restore_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    tx = db.get(Transaction, tx_id)
    if tx is None or tx.deleted_at is None:
        raise HTTPException(404, "流水不在回收站中")
    tx.deleted_at = None
    log_action(db, admin.id, "restore", "transaction", tx.id, after=serialize_tx(tx))
    db.commit()
    db.refresh(tx)
    return serialize_tx(tx)
