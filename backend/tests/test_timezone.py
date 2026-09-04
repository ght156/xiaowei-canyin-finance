"""北京时区（Asia/Shanghai）业务日期测试。

模拟 UTC 服务器：北京时间 2026-09-05 00:30 = UTC 2026-09-04 16:30，
流水/统计必须落在 9 月 5 日。
"""
from datetime import datetime, timezone

import pytest

import app.tz as tz


@pytest.fixture
def utc_fixed(monkeypatch):
    def _set(y, mo, d, h, mi):
        monkeypatch.setattr(tz, "_utcnow", lambda: datetime(y, mo, d, h, mi, tzinfo=timezone.utc))
    return _set


def test_today_cn_after_beijing_midnight(utc_fixed):
    """UTC 16:30 → 北京 00:30 次日：业务日期必须是 9 月 5 日。"""
    utc_fixed(2026, 9, 4, 16, 30)
    assert tz.today_cn().isoformat() == "2026-09-05"
    assert tz.naive_now().isoformat().startswith("2026-09-05T00:30")


def test_today_cn_before_beijing_midnight(utc_fixed):
    utc_fixed(2026, 9, 4, 15, 30)  # 北京 23:30
    assert tz.today_cn().isoformat() == "2026-09-04"


def test_daily_report_uses_beijing_today(client, admin_headers, utc_fixed):
    """即使服务器时钟是 UTC，"今日"报表也必须按北京时间。"""
    utc_fixed(2026, 9, 4, 16, 30)
    data = client.get("/api/reports/daily", headers=admin_headers).json()
    assert data["start_date"] == "2026-09-05"
    assert data["end_date"] == "2026-09-05"


def test_overview_month_boundary_beijing(client, admin_headers, utc_fixed):
    """UTC 8 月 31 日 16:30 → 北京 9 月 1 日 00:30：首页"今日/趋势"进入 9 月。"""
    utc_fixed(2026, 8, 31, 16, 30)
    data = client.get("/api/reports/overview", headers=admin_headers).json()
    assert data["trend"][-1]["date"] == "2026-09-01"


def test_overview_yesterday_field(client, admin_headers, owner_headers, ids):
    """首页新增昨日对比数据。"""
    from tests.conftest import add_tx

    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
           category_id=ids["yingye"], amount="100.00", biz_date="2026-01-10")
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
           category_id=ids["yingye"], amount="30.00", biz_date="2026-01-09")
    data = client.get("/api/reports/overview", headers=admin_headers).json()
    assert "yesterday" in data
