"""店铺管理：所有用户可读，管理员可增改。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Shop, User
from ..schemas import ShopCreate, ShopOut, ShopUpdate
from ..security import get_current_user, require_admin
from ..services.audit import log_action

router = APIRouter(prefix="/api/shops", tags=["shops"])


@router.get("", response_model=list[ShopOut])
def list_shops(
    include_disabled: str = "false",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Shop).order_by(Shop.id)
    if not (include_disabled in ("1", "true") and user.role == "admin"):
        q = q.where(Shop.status == "active")
    return db.scalars(q).all()


@router.post("", response_model=ShopOut, status_code=201)
def create_shop(
    body: ShopCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    exists = db.scalar(select(Shop.id).where(Shop.name == body.name.strip()))
    if exists:
        raise HTTPException(400, "店铺名称已存在")
    shop = Shop(name=body.name.strip())
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
    if shop is None:
        raise HTTPException(404, "店铺不存在")
    before = {"name": shop.name, "status": shop.status}
    if body.name is not None:
        new_name = body.name.strip()
        dup = db.scalar(select(Shop.id).where(Shop.name == new_name, Shop.id != shop_id))
        if dup:
            raise HTTPException(400, "店铺名称已存在")
        shop.name = new_name
    if body.status is not None:
        shop.status = body.status
    log_action(db, admin.id, "update", "shop", shop.id, before=before, after={"name": shop.name, "status": shop.status})
    db.commit()
    db.refresh(shop)
    return shop
