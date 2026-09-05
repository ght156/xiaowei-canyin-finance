"""用户店铺授权测试：employee 创建必须显式授权；同名恢复按新请求全量重设权限。"""
from tests.conftest import login, make_user


def _uid(client, admin_headers, username):
    users = client.get("/api/users", headers=admin_headers).json()
    return next(u["id"] for u in users if u["username"] == username)


def _user_shops(client, admin_headers, uid):
    return client.get(f"/api/users/{uid}/shops", headers=admin_headers).json()


# ---------------- 新建用户 ----------------
def test_create_employee_without_shops_rejected(client, admin_headers):
    resp = client.post("/api/users", headers=admin_headers, json={
        "username": "emp_noshops", "password": "abc12345", "role": "employee", "shop_ids": []})
    assert resp.status_code == 400
    assert "员工至少需要选择一个授权店铺。" in resp.json()["detail"]


def test_create_employee_gets_only_assigned_shop(client, admin_headers, ids):
    resp = client.post("/api/users", headers=admin_headers, json={
        "username": "emp_one", "password": "abc12345", "role": "employee",
        "shop_ids": [ids["zaocan"]]})
    assert resp.status_code == 201
    uid = resp.json()["id"]
    info = _user_shops(client, admin_headers, uid)
    assert info["shop_ids"] == [ids["zaocan"]]

    # 只能访问授权的那一家
    emp = login(client, "emp_one", "abc12345")
    ok = client.post("/api/transactions", headers=emp, json={
        "shop_id": ids["zaocan"], "type": "expense", "category_id": 3,
        "amount": "1.00", "payment_method": "cash", "biz_date": "2026-01-10"})
    assert ok.status_code == 201
    denied = client.post("/api/transactions", headers=emp, json={
        "shop_id": ids["mianshi"], "type": "expense", "category_id": 3,
        "amount": "1.00", "payment_method": "cash", "biz_date": "2026-01-10"})
    assert denied.status_code == 403


def test_create_owner_without_shops_binds_all(client, admin_headers, ids):
    resp = client.post("/api/users", headers=admin_headers, json={
        "username": "owner_all", "password": "abc12345", "role": "owner", "shop_ids": []})
    assert resp.status_code == 201
    info = _user_shops(client, admin_headers, resp.json()["id"])
    assert set(info["shop_ids"]) >= {ids["mianshi"], ids["zaocan"]}

    # 该 owner 能在两家店记账
    h = login(client, "owner_all", "abc12345")
    for sid in (ids["mianshi"], ids["zaocan"]):
        resp = client.post("/api/transactions", headers=h, json={
            "shop_id": sid, "type": "income", "category_id": ids["yingye"],
            "amount": "1.00", "payment_method": "cash", "biz_date": "2026-01-10"})
        assert resp.status_code == 201


def test_create_admin_needs_no_shops(client, admin_headers, ids):
    resp = client.post("/api/users", headers=admin_headers, json={
        "username": "admin_x", "password": "abc12345", "role": "admin", "shop_ids": []})
    assert resp.status_code == 201
    info = _user_shops(client, admin_headers, resp.json()["id"])
    assert info["all"] is True and info["shop_ids"] == []
    # admin 可访问任意店铺
    h = login(client, "admin_x", "abc12345")
    resp = client.get("/api/shops", headers=h)
    assert {s["name"] for s in resp.json()} >= {"面食店", "早餐店"}


# ---------------- 同名恢复：授权按新请求全量重设 ----------------
def test_restore_employee_rebinds_to_new_shops(client, admin_headers, ids):
    """删除原授权早餐店的 employee A，再用同名重建并授权面食店：
    恢复后只有面食店权限，旧早餐店权限必须失效。"""
    emp_h = make_user(client, admin_headers, username="emp_a", password="emp12345",
                      role="employee", shop_ids=[ids["zaocan"]])
    uid = _uid(client, admin_headers, "emp_a")

    # 删除 A
    assert client.delete(f"/api/users/{uid}", headers=admin_headers).status_code == 200

    # 同名重建，授权改为面食店
    resp = client.post("/api/users", headers=admin_headers, json={
        "username": "emp_a", "password": "emp12345", "role": "employee",
        "shop_ids": [ids["mianshi"]]})
    assert resp.status_code == 201
    assert resp.json()["id"] == uid

    info = _user_shops(client, admin_headers, uid)
    assert info["shop_ids"] == [ids["mianshi"]]

    new_h = login(client, "emp_a", "emp12345")
    ok = client.post("/api/transactions", headers=new_h, json={
        "shop_id": ids["mianshi"], "type": "expense", "category_id": 3,
        "amount": "2.00", "payment_method": "cash", "biz_date": "2026-01-10"})
    assert ok.status_code == 201
    denied = client.post("/api/transactions", headers=new_h, json={
        "shop_id": ids["zaocan"], "type": "expense", "category_id": 3,
        "amount": "2.00", "payment_method": "cash", "biz_date": "2026-01-10"})
    assert denied.status_code == 403
    assert "你没有该店铺的操作权限" in denied.json()["detail"]

    # 审计：restore 记录了旧角色/旧店铺 → 新角色/新店铺
    logs = client.get("/api/audit-logs?entity_type=user", headers=admin_headers).json()["items"]
    restore_log = next(l for l in logs if l["action"] == "restore" and l["entity_id"] == uid)
    assert restore_log["before_data"]["role"] == "employee"
    assert restore_log["before_data"]["shops"] == ["早餐店"]
    assert restore_log["after_data"]["role"] == "employee"
    assert restore_log["after_data"]["shops"] == ["面食店"]


def test_restore_employee_as_admin_clears_old_bindings(client, admin_headers, ids):
    """employee 删除后同名恢复成 admin：旧店铺绑定必须清空（admin 默认全部）。"""
    emp_h = make_user(client, admin_headers, username="emp_b", password="emp12345",
                      role="employee", shop_ids=[ids["zaocan"]])
    uid = _uid(client, admin_headers, "emp_b")
    assert client.delete(f"/api/users/{uid}", headers=admin_headers).status_code == 200

    resp = client.post("/api/users", headers=admin_headers, json={
        "username": "emp_b", "password": "admin888", "role": "admin", "shop_ids": []})
    assert resp.status_code == 201

    info = _user_shops(client, admin_headers, uid)
    assert info["all"] is True and info["shop_ids"] == []

    # 恢复后的 admin 能访问全部店铺
    h = login(client, "emp_b", "admin888")
    names = {s["name"] for s in client.get("/api/shops", headers=h).json()}
    assert names >= {"面食店", "早餐店"}


def test_restore_owner_without_shops_binds_all(client, admin_headers, ids):
    """owner 删除后同名恢复且未提供 shop_ids：默认绑定全部 active 店铺。"""
    make_user(client, admin_headers, username="owner_tmp", password="abc12345",
              role="owner", shop_ids=[ids["zaocan"]])
    uid = _uid(client, admin_headers, "owner_tmp")
    client.delete(f"/api/users/{uid}", headers=admin_headers)

    resp = client.post("/api/users", headers=admin_headers, json={
        "username": "owner_tmp", "password": "abc12345", "role": "owner", "shop_ids": []})
    assert resp.status_code == 201
    info = _user_shops(client, admin_headers, uid)
    assert set(info["shop_ids"]) >= {ids["mianshi"], ids["zaocan"]}
