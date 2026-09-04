"""轻量数据库迁移：为旧版本数据库补齐新增列/表数据，保证升级不丢数据。

只做增量变更（SQLite 支持加空列），全部幂等，可重复执行。
"""
import sqlalchemy
from sqlalchemy import select

from .database import SessionLocal, engine

# (表名, 列名, DDL)
_ADD_COLUMN_MIGRATIONS = [
    ("users", "deleted_at", "ALTER TABLE users ADD COLUMN deleted_at DATETIME"),
    ("shops", "deleted_at", "ALTER TABLE shops ADD COLUMN deleted_at DATETIME"),
    ("categories", "deleted_at", "ALTER TABLE categories ADD COLUMN deleted_at DATETIME"),
]


def ensure_schema_upgrades(target_engine: sqlalchemy.Engine | None = None) -> None:
    eng = target_engine or engine
    with eng.connect() as conn:
        for table, column, ddl in _ADD_COLUMN_MIGRATIONS:
            rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            if not rows:
                continue  # 表还不存在（新库由 create_all 直接建全）
            existing = {row[1] for row in rows}
            if column not in existing:
                conn.exec_driver_sql(ddl)
        conn.commit()


def bind_owners_to_active_shops() -> None:
    """V1.2 升级迁移：把每个 owner 用户绑定到当前全部未删除店铺（幂等）。

    admin 默认拥有全部店铺权限，无需绑定。
    老库升级后 owner 立即可用，不需要删除 app.db 重新 seed。
    """
    from .models import Shop, User, UserShop

    with SessionLocal() as db:
        owners = db.scalars(
            select(User).where(User.role == "owner", User.deleted_at.is_(None))
        ).all()
        shops = db.scalars(select(Shop).where(Shop.deleted_at.is_(None))).all()
        changed = False
        for owner in owners:
            have = {link.shop_id for link in owner.shop_links}
            for shop in shops:
                if shop.id not in have:
                    db.add(UserShop(user_id=owner.id, shop_id=shop.id))
                    changed = True
        if changed:
            db.commit()
