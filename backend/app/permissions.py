"""店铺级权限：owner/employee 只能访问被授权（user_shops）的店铺，admin 默认全部。

后端强制校验；前端隐藏菜单仅用于体验。
"""
from fastapi import HTTPException
from sqlalchemy import select

from .models import Shop, Transaction, User, UserShop


def authorized_shop_ids(db, user: User) -> list[int] | None:
    """返回用户可访问的店铺 id 列表；admin 返回 None 表示不限（全部店铺）。"""
    if user.role == "admin":
        return None
    return list(
        db.scalars(
            select(UserShop.shop_id)
            .where(UserShop.user_id == user.id)
            .order_by(UserShop.shop_id)
        )
    )


def ensure_shop_access(db, user: User, shop_id: int) -> None:
    """校验单个店铺访问权限，未授权返回 403。"""
    allowed = authorized_shop_ids(db, user)
    if allowed is not None and shop_id not in allowed:
        raise HTTPException(403, "你没有该店铺的操作权限。")


def shop_ids_or_all(db, user: User) -> list[int] | None:
    """语义别名：汇总类查询的店铺范围。"""
    return authorized_shop_ids(db, user)


def apply_shop_scope(q, db, user: User):
    """给 select(Transaction)/query(Transaction) 追加店铺范围过滤；admin 不过滤。"""
    allowed = authorized_shop_ids(db, user)
    if allowed is not None:
        if not allowed:
            # 没有任何授权店铺：返回空集
            q = q.where(Transaction.shop_id == -1)
        else:
            q = q.where(Transaction.shop_id.in_(allowed))
    return q


def filter_visible_shops(db, shops: list[Shop], user: User) -> list[Shop]:
    """店铺列表按授权过滤（admin 全量）。"""
    allowed = authorized_shop_ids(db, user)
    if allowed is None:
        return shops
    return [s for s in shops if s.id in allowed]
