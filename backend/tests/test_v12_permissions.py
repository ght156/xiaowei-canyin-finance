"""V1.2 权限测试：三层角色 + 店铺级授权（user_shops）。"""
from datetime import datetime, timedelta

from app.migrations import bind_owners_to_active_shops
from app.models import Transaction
from app.database import SessionLocal

from tests.conftest import add_tx, login, make_user


def get_employee_headers(client, admin_headers, ids, username="emp", shop_ids=None):
    return make_user(client, admin_headers, username=username, password="emp12345",
                     role="employee", shop_ids=shop_ids if shop_ids is not None else [ids["zaocan"]])


# 1. employee 可以新增自己授权店铺的流水
def test_employee_can_create_in_own_shop(client, admin_headers, ids):
    emp = get_employee_headers(client, admin_headers, ids)
    tx = add_tx(client, emp, shop_id=ids["zaocan"], tx_type="expense",
                category_id=ids["mianfen"], amount="7.00", biz_date="2026-01-10", remark="员工记的")
    assert tx["created_by_name"] == "emp"


# 2. employee 不能新增其他店铺流水
def test_employee_cannot_create_in_other_shop(client, admin_headers, ids):
    emp = get_employee_headers(client, admin_headers, ids)
    resp = client.post("/api/transactions", headers=emp, json={
        "shop_id": ids["mianshi"], "type": "expense", "category_id": ids["mianfen"],
        "amount": "7.00", "payment_method": "cash", "biz_date": "2026-01-10"})
    assert resp.status_code == 403
    assert "你没有该店铺的操作权限" in resp.json()["detail"]


# 3. employee 不能查看其他店铺流水
def test_employee_cannot_view_other_shop(client, admin_headers, owner_headers, ids):
    tx = add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
                category_id=ids["yingye"], amount="88.00", biz_date="2026-01-10")
    emp = get_employee_headers(client, admin_headers, ids)
    assert client.get(f"/api/transactions?shop_id={ids['mianshi']}", headers=emp).status_code == 403
    assert client.get(f"/api/transactions/{tx['id']}", headers=emp).status_code == 403
    # 列表里也看不到他店流水（只有授权店铺数据）
    data = client.get("/api/transactions", headers=emp).json()
    assert all(item["shop_id"] != ids["mianshi"] for item in data["items"])


# 4. employee 不能查看利润报表 / 经营分析
def test_employee_cannot_view_reports(client, admin_headers, ids):
    emp = get_employee_headers(client, admin_headers, ids)
    for path in [
        "/api/reports/monthly?month=2026-01",
        "/api/reports/daily",
        "/api/reports/overview",
        "/api/reports/range?start=2026-01-01&end=2026-01-31",
        "/api/reports/trend?start=2026-01-01&end=2026-01-31",
        "/api/reports/expense-categories?start=2026-01-01&end=2026-01-31",
    ]:
        resp = client.get(path, headers=emp)
        assert resp.status_code == 403, path


# 4b. 员工专用汇总：只有今日营业额与笔数，无利润字段
def test_employee_summary_no_profit(client, admin_headers, owner_headers, ids):
    emp = get_employee_headers(client, admin_headers, ids)
    from datetime import date as _d
    today = _d.today().isoformat()
    add_tx(client, emp, shop_id=ids["zaocan"], tx_type="income",
           category_id=ids["yingye"], amount="12.00", biz_date=today)
    add_tx(client, owner_headers, shop_id=ids["zaocan"], tx_type="income",
           category_id=ids["yingye"], amount="13.00", biz_date=today)
    data = client.get(f"/api/reports/employee-summary?shop_id={ids['zaocan']}", headers=emp).json()
    assert data["income"] == "25.00"  # 店铺当日全部营业额（含店主录入）
    assert data["count"] == 2
    assert "profit" not in data and "profit_rate" not in data
    # admin/owner 不能用员工接口
    assert client.get("/api/reports/employee-summary", headers=admin_headers).status_code == 403


# 5. employee 不能调用管理员 API
def test_employee_cannot_call_admin_api(client, admin_headers, ids):
    emp = get_employee_headers(client, admin_headers, ids)
    assert client.get("/api/users", headers=emp).status_code == 403
    assert client.get("/api/audit-logs", headers=emp).status_code == 403
    assert client.get("/api/backups", headers=emp).status_code == 403
    assert client.post("/api/shops", headers=emp, json={"name": "X店"}).status_code == 403
    assert client.post("/api/categories", headers=emp,
                       json={"type": "expense", "name": "X"}).status_code == 403
    assert client.get("/api/export?start=2026-01-01&end=2026-01-31", headers=emp).status_code == 403


# 6/7. employee 不能删除、不能恢复
def test_employee_cannot_delete_or_restore(client, admin_headers, owner_headers, ids):
    tx = add_tx(client, owner_headers, shop_id=ids["zaocan"], tx_type="income",
                category_id=ids["yingye"], amount="9.00", biz_date="2026-01-10")
    emp = get_employee_headers(client, admin_headers, ids)
    assert client.delete(f"/api/transactions/{tx['id']}", headers=emp).status_code == 403

    client.delete(f"/api/transactions/{tx['id']}", headers=owner_headers)  # owner 删除
    resp = client.post(f"/api/transactions/{tx['id']}/restore", headers=emp)
    assert resp.status_code == 403


# 8/9. employee 只能修改自己 10 分钟内创建的流水
def test_employee_edit_window(client, admin_headers, owner_headers, ids):
    from datetime import date as _d
    emp = get_employee_headers(client, admin_headers, ids, username="emp_edit")
    today = _d.today().isoformat()
    tx = add_tx(client, emp, shop_id=ids["zaocan"], tx_type="income",
                category_id=ids["yingye"], amount="5.00", biz_date=today)

    # 自己的、10 分钟内 → 可改
    resp = client.put(f"/api/transactions/{tx['id']}", headers=emp, json={"remark": "刚记错改一下"})
    assert resp.status_code == 200

    # 把创建时间改到 11 分钟前 → 超时不可改
    with SessionLocal() as db:
        row = db.get(Transaction, tx["id"])
        row.created_at = datetime.now() - timedelta(minutes=11)
        db.commit()
    resp = client.put(f"/api/transactions/{tx['id']}", headers=emp, json={"remark": "晚了"})
    assert resp.status_code == 403
    assert "该流水已超过可自行修改时间，请联系店主修改。" in resp.json()["detail"]

    # 店主不受 10 分钟限制
    resp = client.put(f"/api/transactions/{tx['id']}", headers=owner_headers, json={"remark": "店主改"})
    assert resp.status_code == 200


# 10. owner 可以查看授权店铺完整经营数据
def test_owner_full_reports_on_authorized_shops(client, owner_headers, ids):
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
           category_id=ids["yingye"], amount="100.00", biz_date="2026-01-10")
    monthly = client.get("/api/reports/monthly?month=2026-01", headers=owner_headers).json()
    assert monthly["income"] == "100.00"
    assert client.get("/api/reports/overview", headers=owner_headers).status_code == 200


# 11. owner 不能查看未授权店铺
def test_owner_cannot_access_unauthorized_shop(client, admin_headers, owner_headers, ids):
    shop3 = client.post("/api/shops", headers=admin_headers, json={"name": "烧烤店"}).json()
    add_tx(client, admin_headers, shop_id=shop3["id"], tx_type="income",
           category_id=ids["yingye"], amount="77.00", biz_date="2026-01-10")

    # owner 未被授权新店铺
    shops = {s["id"] for s in client.get("/api/shops", headers=owner_headers).json()}
    assert shop3["id"] not in shops
    assert client.get(f"/api/reports/monthly?month=2026-01&shop_id={shop3['id']}",
                      headers=owner_headers).status_code == 403
    assert client.get(f"/api/transactions?shop_id={shop3['id']}",
                      headers=owner_headers).status_code == 403
    # 汇总里也看不到未授权店铺
    monthly = client.get("/api/reports/monthly?month=2026-01", headers=owner_headers).json()
    assert all(s["shop_id"] != shop3["id"] for s in monthly["by_shop"])


# 12. owner 可以修改自己店铺流水
def test_owner_can_edit_own_shop_tx(client, owner_headers, ids):
    tx = add_tx(client, owner_headers, shop_id=ids["zaocan"], tx_type="expense",
                category_id=ids["mianfen"], amount="3.00", biz_date="2026-01-10")
    resp = client.put(f"/api/transactions/{tx['id']}", headers=owner_headers,
                      json={"amount": "4.00"})
    assert resp.status_code == 200
    assert resp.json()["amount"] == "4.00"


# 13. owner 不能恢复整个数据库（恢复/下载/列表均 admin 专属）
def test_owner_cannot_restore_database(client, admin_headers, owner_headers):
    client.post("/api/backups", headers=admin_headers)
    backups = client.get("/api/backups", headers=admin_headers).json()
    name = backups[0]["file_name"]
    assert client.post(f"/api/backups/{name}/restore", headers=owner_headers).status_code == 403
    assert client.get(f"/api/backups/{name}/download", headers=owner_headers).status_code == 403
    assert client.get("/api/backups", headers=owner_headers).status_code == 403


# 14. admin 可以访问所有店铺
def test_admin_access_all_shops(client, admin_headers, ids):
    shops = {s["id"] for s in client.get("/api/shops", headers=admin_headers).json()}
    assert ids["mianshi"] in shops and ids["zaocan"] in shops
    for sid in shops:
        resp = client.post("/api/transactions", headers=admin_headers, json={
            "shop_id": sid, "type": "income", "category_id": ids["yingye"],
            "amount": "1.00", "payment_method": "cash", "biz_date": "2026-01-10"})
        assert resp.status_code == 201


# 15. 系统仍至少保留一个 active admin（含角色修改路径）
def test_last_admin_protection_still_enforced(client, admin_headers):
    me = client.get("/api/auth/me", headers=admin_headers).json()
    resp = client.put(f"/api/users/{me['id']}", headers=admin_headers, json={"role": "owner"})
    assert resp.status_code == 400
    # owner/employee 无权创建管理员
    owner_h = login(client, "owner", "owner123")
    assert client.post("/api/users", headers=owner_h,
                       json={"username": "hacker", "password": "abc12345", "role": "admin"}).status_code == 403
    # 非法角色 422
    resp = client.post("/api/users", headers=admin_headers,
                       json={"username": "bad", "password": "abc12345", "role": "manager"})
    assert resp.status_code == 422


# 16. 修改 user_shops 权限后立即生效
def test_user_shops_changes_take_effect_immediately(client, admin_headers, ids):
    emp = get_employee_headers(client, admin_headers, ids, username="emp_dyn")

    # 初始只有早餐店：面食店被拒
    body = {"shop_id": ids["mianshi"], "type": "expense", "category_id": ids["mianfen"],
            "amount": "2.00", "payment_method": "cash", "biz_date": "2026-01-10"}
    assert client.post("/api/transactions", headers=emp, json=body).status_code == 403

    # 授权面食店后立即可用
    resp = client.put(f"/api/users/{_uid(client, admin_headers, 'emp_dyn')}/shops",
                      headers=admin_headers, json={"shop_ids": [ids["zaocan"], ids["mianshi"]]})
    assert resp.status_code == 200
    assert client.post("/api/transactions", headers=emp, json=body).status_code == 201

    # 再收回 → 立即失效
    client.put(f"/api/users/{_uid(client, admin_headers, 'emp_dyn')}/shops",
               headers=admin_headers, json={"shop_ids": [ids["zaocan"]]})
    assert client.post("/api/transactions", headers=emp, json=body).status_code == 403

    # 授权变更写入审计（前后店铺名列表）
    logs = client.get("/api/audit-logs?entity_type=user", headers=admin_headers).json()["items"]
    # 找"新增面食店授权"那一条（after 为 早餐店+面食店）
    shop_log = next(l for l in logs if l["action"] == "update_shops"
                    and set(l["after_data"]["shops"]) == {"早餐店", "面食店"}
                    and l["before_data"]["shops"] == ["早餐店"])


def _uid(client, admin_headers, username):
    users = client.get("/api/users", headers=admin_headers).json()
    return next(u["id"] for u in users if u["username"] == username)


# 17. 升级迁移：owner 自动绑定全部店铺
def test_owner_binding_migration(client, admin_headers, ids):
    from app.models import UserShop

    owner_id = 2
    with SessionLocal() as db:
        db.query(UserShop).filter(UserShop.user_id == owner_id).delete()
        db.commit()
    bind_owners_to_active_shops()
    resp = client.get(f"/api/users/{owner_id}/shops", headers=admin_headers).json()
    assert set(resp["shop_ids"]) >= {ids["mianshi"], ids["zaocan"]}
