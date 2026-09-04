"""记账与金额精度测试：整数分存储，杜绝浮点误差。"""

from tests.conftest import add_tx


def test_create_income_and_amount_roundtrip(client, owner_headers, ids):
    tx = add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
                category_id=ids["yingye"], amount="123.45", biz_date="2026-01-10", remark="午餐收入")
    assert tx["amount"] == "123.45"
    assert tx["shop_name"] == "面食店"
    assert tx["category_name"] == "营业收入"


def test_amount_precision_no_float_error(client, owner_headers, ids):
    # 经典浮点陷阱：0.1 + 0.2；系统必须精确存取
    tx = add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
                category_id=ids["yingye"], amount="0.1", biz_date="2026-01-10")
    assert tx["amount"] == "0.10"
    tx = add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
                category_id=ids["yingye"], amount="0.2", biz_date="2026-01-10")
    assert tx["amount"] == "0.20"


def test_amount_zero_rejected(client, owner_headers, ids):
    resp = client.post("/api/transactions", headers=owner_headers, json={
        "shop_id": ids["mianshi"], "type": "income", "category_id": ids["yingye"],
        "amount": "0", "payment_method": "cash", "biz_date": "2026-01-10",
    })
    assert resp.status_code == 422


def test_amount_too_many_decimals_rejected(client, owner_headers, ids):
    resp = client.post("/api/transactions", headers=owner_headers, json={
        "shop_id": ids["mianshi"], "type": "income", "category_id": ids["yingye"],
        "amount": "12.345", "payment_method": "cash", "biz_date": "2026-01-10",
    })
    assert resp.status_code == 422


def test_amount_negative_rejected_by_pattern(client, owner_headers, ids):
    resp = client.post("/api/transactions", headers=owner_headers, json={
        "shop_id": ids["mianshi"], "type": "income", "category_id": ids["yingye"],
        "amount": "-5.00", "payment_method": "cash", "biz_date": "2026-01-10",
    })
    assert resp.status_code == 422


def test_category_type_mismatch_rejected(client, owner_headers, ids):
    resp = client.post("/api/transactions", headers=owner_headers, json={
        "shop_id": ids["mianshi"], "type": "income", "category_id": ids["mianfen"],
        "amount": "10.00", "payment_method": "cash", "biz_date": "2026-01-10",
    })
    assert resp.status_code == 400


def test_create_requires_auth(client, ids):
    resp = client.post("/api/transactions", json={
        "shop_id": ids["mianshi"], "type": "income", "category_id": ids["yingye"],
        "amount": "10.00", "payment_method": "cash", "biz_date": "2026-01-10",
    })
    assert resp.status_code == 401


def test_list_filters(client, owner_headers, ids):
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
           category_id=ids["yingye"], amount="100.00", biz_date="2026-01-10", remark="早市")
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="expense",
           category_id=ids["mianfen"], amount="30.00", biz_date="2026-01-11", remark="买面粉")
    add_tx(client, owner_headers, shop_id=ids["zaocan"], tx_type="income",
           category_id=ids["yingye"], amount="50.00", biz_date="2026-01-12", remark="早市")

    # 按类型
    data = client.get("/api/transactions?type=expense", headers=owner_headers).json()
    assert data["total"] == 1 and data["items"][0]["remark"] == "买面粉"
    # 按店铺
    data = client.get(f"/api/transactions?shop_id={ids['zaocan']}", headers=owner_headers).json()
    assert data["total"] == 1
    # 按日期区间
    data = client.get("/api/transactions?start_date=2026-01-10&end_date=2026-01-11", headers=owner_headers).json()
    assert data["total"] == 2
    # 按关键字
    data = client.get("/api/transactions?keyword=面粉", headers=owner_headers).json()
    assert data["total"] == 1
    # 按分类
    data = client.get(f"/api/transactions?category_id={ids['yingye']}", headers=owner_headers).json()
    assert data["total"] == 2


def test_list_pagination(client, owner_headers, ids):
    for i in range(5):
        add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
               category_id=ids["yingye"], amount="10.00", biz_date="2026-01-10")
    data = client.get("/api/transactions?page=2&page_size=2", headers=owner_headers).json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
