"""审计日志：关键数据的修改前后值、操作者、时间。"""
from datetime import date, datetime

from sqlalchemy.orm import Session

from ..models import AuditLog


def _json_safe(value):
    """把 date/datetime 等对象转为 JSON 可序列化的字符串。"""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def log_action(
    db: Session,
    user_id: int,
    action: str,
    entity_type: str,
    entity_id: int | None,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_data=_json_safe(before),
            after_data=_json_safe(after),
        )
    )
