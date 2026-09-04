"""利润统计测试：单店铺/合并、区间边界、收入为 0、分类构成、首页总览。"""

from tests.conftest import add_tx


def seed_monthly_data(client, owner_headers, ids):
    """2026-01：面食店收入 300、支出 30；早餐店收入 50、支出 20.25。"""
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
           category_id=ids["yingye"], amount="100.00", biz_date="2026-01-10")
    add_tx(client, owner_headers, shop_id=ids["zaocan"], tx_type="income",
           category_id=ids["yingye"], amount="50.00", biz_date="2026-01-10")
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="expense",
           category_id=ids["mianfen"], amount="30.00", biz_date="2026-01-10")
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
           category_id=ids["yingye"], amount="200.00", biz_date="2026-01-20")
    add_tx(client, owner_headers, shop_id=ids["zaocan"], tx_type="expense",
           category_id=ids["fangzu"], amount="20.25", biz_date="2026-01-20")
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
           category_id=ids["yingye"], amount="10.00", biz_date="2026-02-05")


def test_monthly_all_shops(client, owner_headers, ids):
    seed_monthly_data(client, owner_headers, ids)
    data = client.get("/api/reports/monthly?month=2026-01", headers=owner_headers).json()
    assert data["income"] == "350.00"
    assert data["expense"] == "50.25"
    assert data["profit"] == "299.75"
    # 299.75 / 350.00 = 85.6428...% → 85.6%
    assert data["profit_rate"] == "85.6%"


def test_monthly_single_shop(client, owner_headers, ids):
    seed_monthly_data(client, owner_headers, ids)
    data = client.get(f"/api/reports/monthly?month=2026-01&shop_id={ids['mianshi']}", headers=owner_headers).json()
    assert data["income"] == "300.00"
    assert data["expense"] == "30.00"
    assert data["profit"] == "270.00"
    by_shop = {s["shop_name"]: s for s in data["by_shop"]}
    assert by_shop["面食店"]["income"] == "300.00"
    assert "早餐店" not in by_shop  # 该店铺在此查询下无数据


def test_range_report(client, owner_headers, ids):
    seed_monthly_data(client, owner_headers, ids)
    data = client.get(f"/api/reports/range?start=2026-01-01&end=2026-01-31&shop_id={ids['zaocan']}",
                      headers=owner_headers).json()
    assert data["income"] == "50.00"
    assert data["expense"] == "20.25"
    assert data["profit"] == "29.75"
    # 29.75 / 50.00 = 59.5%
    assert data["profit_rate"] == "59.5%"


def test_range_boundary_inclusive(client, owner_headers, ids):
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
           category_id=ids["yingye"], amount="8.00", biz_date="2026-01-01")
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
           category_id=ids["yingye"], amount="9.00", biz_date="2026-01-31")
    data = client.get("/api/reports/range?start=2026-01-01&end=2026-01-31", headers=owner_headers).json()
    assert data["income"] == "17.00"


def test_daily_report(client, owner_headers, ids):
    seed_monthly_data(client, owner_headers, ids)
    data = client.get("/api/reports/daily?date=2026-01-10", headers=owner_headers).json()
    assert data["income"] == "150.00"
    assert data["expense"] == "30.00"
    assert data["profit"] == "120.00"


def test_zero_income_profit_rate_is_none(client, owner_headers, ids):
    """收入为 0 时利润率应为 null（前端显示 —），不能除零报错。"""
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="expense",
           category_id=ids["mianfen"], amount="15.00", biz_date="2026-03-08")
    data = client.get("/api/reports/monthly?month=2026-03", headers=owner_headers).json()
    assert data["income"] == "0.00"
    assert data["expense"] == "15.00"
    assert data["profit"] == "-15.00"
    assert data["profit_rate"] is None


def test_expense_categories_breakdown(client, owner_headers, ids):
    seed_monthly_data(client, owner_headers, ids)
    data = client.get("/api/reports/expense-categories?start=2026-01-01&end=2026-01-31",
                      headers=owner_headers).json()
    assert len(data) == 2
    # 按金额降序：面粉 30.00 (59.7%) > 房租 20.25 (40.3%)
    assert data[0]["category_name"] == "面粉/米面"
    assert data[0]["amount"] == "30.00"
    assert data[0]["percentage"] == "59.7%"
    assert data[1]["category_name"] == "房租"
    assert data[1]["percentage"] == "40.3%"


def test_overview_shape(client, owner_headers, ids):
    resp = client.get("/api/reports/overview", headers=owner_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) >= {"today", "month", "trend", "shop_name"}
    assert data["shop_name"] == "全部店铺"
    assert len(data["trend"]) == 7
    resp = client.get(f"/api/reports/overview?shop_id={ids['mianshi']}", headers=owner_headers).json()
    assert resp["shop_name"] == "面食店"


def test_reports_require_auth(client):
    assert client.get("/api/reports/monthly?month=2026-01").status_code == 401
