"""收支分类管理：所有用户可读（启用中的），管理员可增改删。

删除为软删除：分类从选择列表移除，历史流水的分类名照常保留；
重建同名分类时自动恢复原记录。
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, User
from ..schemas import CategoryCreate, CategoryOut, CategoryUpdate
from ..security import get_current_user, require_admin
from ..services.audit import log_action
from ..tz import naive_now

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(
    type: Literal["income", "expense"] | None = None,
    include_disabled: str = "false",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = (
        select(Category)
        .where(Category.deleted_at.is_(None))
        .order_by(Category.type, Category.sort_order, Category.id)
    )
    if type is not None:
        q = q.where(Category.type == type)
    if not (include_disabled in ("1", "true") and user.role == "admin"):
        q = q.where(Category.status == "active")
    return db.scalars(q).all()


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(
    body: CategoryCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    name = body.name.strip()
    existing = db.scalar(
        select(Category).where(Category.type == body.type, Category.name == name)
    )
    if existing and existing.deleted_at is None:
        raise HTTPException(400, "分类已存在")
    if existing:
        # 同名分类曾被删除：恢复原记录（历史流水自动接上）
        existing.deleted_at = None
        existing.status = "active"
        existing.sort_order = body.sort_order
        log_action(db, admin.id, "restore", "category", existing.id,
                   after={"type": existing.type, "name": name})
        db.commit()
        db.refresh(existing)
        return existing

    cat = Category(type=body.type, name=name, sort_order=body.sort_order)
    db.add(cat)
    db.flush()
    log_action(db, admin.id, "create", "category", cat.id, after={"type": cat.type, "name": cat.name})
    db.commit()
    db.refresh(cat)
    return cat


@router.put("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    body: CategoryUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    cat = db.get(Category, category_id)
    if cat is None or cat.deleted_at is not None:
        raise HTTPException(404, "分类不存在")
    before = {"name": cat.name, "sort_order": cat.sort_order, "status": cat.status}
    if body.name is not None:
        new_name = body.name.strip()
        dup = db.scalar(
            select(Category.id).where(
                Category.type == cat.type, Category.name == new_name,
                Category.id != category_id, Category.deleted_at.is_(None),
            )
        )
        if dup:
            raise HTTPException(400, "分类已存在")
        cat.name = new_name
    if body.sort_order is not None:
        cat.sort_order = body.sort_order
    if body.status is not None:
        cat.status = body.status
    log_action(
        db, admin.id, "update", "category", cat.id,
        before=before,
        after={"name": cat.name, "sort_order": cat.sort_order, "status": cat.status},
    )
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """软删除分类：从选择列表移除，历史流水的分类名保留。"""
    cat = db.get(Category, category_id)
    if cat is None or cat.deleted_at is not None:
        raise HTTPException(404, "分类不存在")

    before = {"type": cat.type, "name": cat.name}
    cat.deleted_at = naive_now()
    cat.status = "disabled"
    log_action(db, admin.id, "delete", "category", cat.id, before=before)
    db.commit()
    return {"ok": True, "message": "分类已删除，历史流水的分类名仍保留"}
