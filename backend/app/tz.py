"""统一业务时间：全部按北京时间（Asia/Shanghai）计算。

经营地点在中国，业务日期（"今天"、"本月"、备份日期、流水时间）必须与北京时间一致，
不依赖服务器本地时区（例如部署到 UTC 云服务器时凌晨 0～8 点不能算到前一天）。

数据库中时间统一存"北京时间的 naive datetime"，与 V1.0 已有数据格式保持一致。
"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo("Asia/Shanghai")

# 可注入的 UTC 当前时间（测试用 monkeypatch 覆盖）
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def now_cn() -> datetime:
    """当前北京时间（带时区）。"""
    return _utcnow().astimezone(CN_TZ)


def naive_now() -> datetime:
    """当前北京时间（naive，用于数据库存储）。"""
    return now_cn().replace(tzinfo=None)


def today_cn() -> date:
    """当前北京日期。"""
    return now_cn().date()
