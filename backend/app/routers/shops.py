"""店铺管理：所有用户可读，管理员可增改删。

删除为软删除：店铺从选择列表移除，但历史流水、统计中的店铺名照常保留。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Shop, User
from ..schemas import ShopCreate, ShopOut, ShopUpdate
from ..security import get_current_user, require_admin
from ..services.audit import log_action
from ..tz import naive_now

router = APIRouter(prefix="/api/shops", tags=["shops"])


@router.get("", response_model=list[ShopOut])
def list_shops(
    include_disabled: str = "false",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Shop).where(Shop.deleted_at.is_(None)).order_by(Shop.id)
    if not (include_disabled in ("1", "true") and user.role == "admin"):
        q = q.where(Shop.status == "active")
    return db.scalars(q).all()


@router.post("", response_model=ShopOut, status_code=201)
def create_shop(
    body: ShopCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    name = body.name.strip()
    existing = db.scalar(select(Shop).where(Shop.name == name))
    if existing and existing.deleted_at is None:
        raise HTTPException(400, "店铺名称已存在")
    if existing:
        # 同名店铺曾被删除：恢复原记录（历史流水自动接上）
        existing.deleted_at = None
        existing.status = "active"
        log_action(db, admin.id, "restore", "shop", existing.id, after={"name": name})
        db.commit()
        db.refresh(existing)
        return existing

    shop = Shop(name=name)
    db.add(shop)
    db.flush()
    log_action(db, admin.id, "create", "shop", shop.id, after={"name": shop.name})
    db.commit()
    db.refresh(shop)
    return shop


@router.put("/{shop_id}", response_model=ShopOut)
def update_shop(
    shop_id: int,
    body: ShopUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    shop = db.get(Shop, shop_id)
    if shop is None or shop.deleted_at is not None:
        raise HTTPException(404, "店铺不存在")
    before = {"name": shop.name, "status": shop.status}
    if body.name is not None:
        new_name = body.name.strip()
        dup = db.scalar(
            select(Shop.id).where(
                Shop.name == new_name, Shop.id != shop_id, Shop.deleted_at.is_(None)
            )
        )
        if dup:
            raise HTTPException(400, "店铺名称已存在")
        shop.name = new_name
    if body.status is not None:
        shop.status = body.status
    log_action(db, admin.id, "update", "shop", shop.id, before=before, after={"name": shop.name, "status": shop.status})
    db.commit()
    db.refresh(shop)
    return shop


@router.delete("/{shop_id}")
def delete_shop(
    shop_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """软删除店铺：从选择列表移除，历史流水与统计中的店铺名保留。"""
    shop = db.get(Shop, shop_id)
    if shop is None or shop.deleted_at is not None:
        raise HTTPException(404, "店铺不存在")

    alive = db.scalar(
        select(func.count(Shop.id)).where(Shop.deleted_at.is_(None), Shop.id != shop_id)
    )
    if not alive:
        raise HTTPException(400, "系统至少需要保留一个店铺")

    before = {"name": shop.name, "status": shop.status}
    shop.deleted_at = naive_now()
    shop.status = "disabled"
    log_action(db, admin.id, "delete", "shop", shop.id, before=before)
    db.commit()
    return {"ok": True, "message": "店铺已删除，历史流水与统计仍保留该店铺名"}
