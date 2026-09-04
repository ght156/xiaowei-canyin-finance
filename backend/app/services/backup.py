"""数据库备份与恢复。

- 备份使用 SQLite 在线备份 API，复制期间业务可正常进行。
- 备份类型 backup_type：auto（每日自动）/ manual（手动）/ pre_restore（恢复前安全备份）。
- 恢复流程：校验目标文件 → 创建安全备份 → 恢复 → 校验，失败自动回滚，绝不留半损坏状态。
"""
from pathlib import Path

import sqlite3
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import BACKUP_DIR, BACKUP_KEEP, DB_PATH
from ..models import BackupRecord
from ..tz import naive_now

# 恢复前要求备份文件必须包含的关键表
REQUIRED_TABLES = {"users", "shops", "categories", "transactions", "audit_logs"}

PRE_RESTORE_KEEP = 5  # 安全备份单独保留最近 5 份


def _valid_backup_name(file_name: str) -> bool:
    return bool(file_name) and "/" not in file_name and "\\" not in file_name and ".." not in file_name


def validate_backup_file(path: Path) -> None:
    """校验备份文件：存在、可打开的 SQLite、关键表齐全、快速完整性检查通过。"""
    if not path.exists():
        raise FileNotFoundError("备份文件不存在")
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            missing = REQUIRED_TABLES - tables
            if missing:
                raise ValueError(f"备份文件缺少关键数据表：{', '.join(sorted(missing))}")
            result = conn.execute("PRAGMA quick_check").fetchone()
            if not result or result[0] != "ok":
                raise ValueError("备份文件完整性检查未通过")
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        raise ValueError("备份文件不是有效的 SQLite 数据库")


def create_backup(db: Session, backup_type: str = "manual") -> BackupRecord:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = naive_now().strftime("%Y%m%d_%H%M%S")
    prefix = "pre_restore" if backup_type == "pre_restore" else "backup"
    dest = BACKUP_DIR / f"{prefix}_{ts}.db"

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
    """普通备份保留最近 BACKUP_KEEP 份，恢复前安全备份保留最近 PRE_RESTORE_KEEP 份。"""
    for prefix, keep in (("backup_", BACKUP_KEEP), ("pre_restore_", PRE_RESTORE_KEEP)):
        records = db.scalars(
            select(BackupRecord)
            .where(BackupRecord.file_name.like(f"{prefix}%"))
            .order_by(BackupRecord.created_at.desc(), BackupRecord.id.desc())
        ).all()
        for old in records[keep:]:
            _delete_backup_file(old.file_name)
            db.delete(old)
    db.commit()


def _delete_backup_file(file_name: str) -> None:
    path = BACKUP_DIR / file_name
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


def maybe_auto_backup(db: Session) -> bool:
    """每天（按北京时间）第一次触发时自动备份一次。返回是否创建了备份。"""
    today_start = naive_now().replace(hour=0, minute=0, second=0, microsecond=0)
    exists = db.scalar(
        select(BackupRecord.id)
        .where(BackupRecord.backup_type == "auto", BackupRecord.created_at >= today_start)
        .limit(1)
    )
    if exists is None:
        create_backup(db, backup_type="auto")
        return True
    return False


def _backup_into_live(source: Path) -> None:
    """把 source 文件的内容通过 SQLite 在线备份 API 写入当前数据库。"""
    src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(DB_PATH))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def restore_backup(db: Session, file_name: str) -> BackupRecord:
    """从指定备份恢复当前数据库。

    流程：校验目标文件 → 创建恢复前安全备份 → 恢复 → 校验。
    恢复过程中任何一步失败，都会用安全备份把当前数据库恢复原状。
    返回恢复前创建的安全备份记录。
    """
    if not _valid_backup_name(file_name):
        raise ValueError("非法文件名")
    target = BACKUP_DIR / file_name
    validate_backup_file(target)

    # ① 恢复前安全备份（safety backup）
    safety = create_backup(db, backup_type="pre_restore")
    safety_path = BACKUP_DIR / safety.file_name

    try:
        # ② 执行恢复
        _backup_into_live(target)
        # ③ 恢复后校验当前数据库可用
        validate_backup_file(DB_PATH)
    except Exception:
        # ④ 失败回滚：把安全备份写回当前数据库
        try:
            _backup_into_live(safety_path)
        except sqlite3.DatabaseError:
            pass
        raise

    # 恢复会把 backup_records 一并回滚到备份时间点，安全备份记录需要重新登记，
    # 保证"这次恢复之前发生过一次安全备份"始终可追溯（文件 + 记录都在）。
    db.add(
        BackupRecord(
            file_name=safety.file_name, backup_type="pre_restore", status="success"
        )
    )
    db.commit()
    return safety
