"""轻量数据库迁移：为旧版本数据库补齐新增列，保证升级不丢数据。

只做增量列补充（SQLite 支持 ALTER TABLE ADD COLUMN 空列），
所有新列均可为 NULL，旧行为 NULL 即表示"未删除"。
"""
import sqlalchemy

from .database import engine

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
