"""登录、JWT、RBAC 权限校验测试。"""


def test_login_ok(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"]
    assert data["user"]["role"] == "admin"


def test_login_wrong_password(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "bad"})
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/api/auth/login", json={"username": "nobody", "password": "x123456"})
    assert resp.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_token(client, admin_headers):
    resp = client.get("/api/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


def test_me_with_bad_token(client):
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer bad.token.here"}).status_code == 401


def test_owner_cannot_manage_shops(client, owner_headers):
    resp = client.post("/api/shops", headers=owner_headers, json={"name": "新店铺"})
    assert resp.status_code == 403


def test_admin_can_create_shop(client, admin_headers):
    resp = client.post("/api/shops", headers=admin_headers, json={"name": "测试奶茶店"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "测试奶茶店"


def test_duplicate_shop_rejected(client, admin_headers, ids):
    resp = client.post("/api/shops", headers=admin_headers, json={"name": "面食店"})
    assert resp.status_code == 400


def test_owner_cannot_create_category(client, owner_headers):
    resp = client.post(
        "/api/categories", headers=owner_headers, json={"type": "expense", "name": "广告费"}
    )
    assert resp.status_code == 403


def test_admin_can_create_category(client, admin_headers):
    resp = client.post(
        "/api/categories", headers=admin_headers, json={"type": "expense", "name": "广告费", "sort_order": 99}
    )
    assert resp.status_code == 201
    assert resp.json()["sort_order"] == 99


def test_admin_can_disable_category(client, admin_headers, ids):
    resp = client.put(f"/api/categories/{ids['mianfen']}", headers=admin_headers, json={"status": "disabled"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"
    # 恢复
    resp = client.put(f"/api/categories/{ids['mianfen']}", headers=admin_headers, json={"status": "active"})
    assert resp.json()["status"] == "active"


def test_disabled_category_hidden_from_list(client, admin_headers, ids):
    client.put(f"/api/categories/{ids['fangzu']}", headers=admin_headers, json={"status": "disabled"})
    active = {c["id"] for c in client.get("/api/categories", headers=admin_headers).json()}
    assert ids["fangzu"] not in active
    all_cats = {c["id"] for c in client.get("/api/categories?include_disabled=1", headers=admin_headers).json()}
    assert ids["fangzu"] in all_cats
    # 恢复，避免影响其他测试
    client.put(f"/api/categories/{ids['fangzu']}", headers=admin_headers, json={"status": "active"})
