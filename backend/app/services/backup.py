"""数据库备份：SQLite 在线备份 API 复制到 backups/ 目录，保留最近 N 份。"""
from datetime import datetime, timedelta
from pathlib import Path

import sqlite3
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import BACKUP_DIR, BACKUP_KEEP, DB_PATH
from ..models import BackupRecord


def create_backup(db: Session, backup_type: str = "manual") -> BackupRecord:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"backup_{ts}.db"

    src = sqlite3.connect(str(DB_PATH))
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    record = BackupRecord(file_name=dest.name, backup_type=backup_type, status="success")
    db.add(record)
    db.commit()
    db.refresh(record)
    _prune_old_backups(db)
    return record


def _prune_old_backups(db: Session) -> None:
    """只保留最近 BACKUP_KEEP 份备份文件与记录。"""
    records = db.scalars(
        select(BackupRecord).order_by(BackupRecord.created_at.desc(), BackupRecord.id.desc())
    ).all()
    for old in records[BACKUP_KEEP:]:
        path = BACKUP_DIR / old.file_name
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
        db.delete(old)
    db.commit()


def maybe_auto_backup(db: Session) -> None:
    """每天第一次启动时自动备份一次。"""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    exists = db.scalar(
        select(BackupRecord.id)
        .where(BackupRecord.backup_type == "auto", BackupRecord.created_at >= today_start)
        .limit(1)
    )
    if exists is None:
        create_backup(db, backup_type="auto")


def restore_backup(db: Session, file_name: str) -> Path:
    """从指定备份文件恢复数据库（覆盖当前库文件）。"""
    if "/" in file_name or "\\" in file_name or ".." in file_name:
        raise ValueError("非法文件名")
    src = BACKUP_DIR / file_name
    if not src.exists():
        raise FileNotFoundError("备份文件不存在")

    s = sqlite3.connect(str(src))
    try:
        d = sqlite3.connect(str(DB_PATH))
        try:
            d.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            s.backup(d)
        finally:
            d.close()
    finally:
        s.close()
    return src


def restore_since_days(days: int) -> None:  # pragma: no cover - 预留
    _ = timedelta(days=days)
