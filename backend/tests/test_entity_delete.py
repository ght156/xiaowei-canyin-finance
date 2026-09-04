"""用户/分类/店铺软删除测试：删除后历史记录保留、保护规则、同名重建即恢复、旧库迁移。"""
from sqlalchemy import create_engine

from app.migrations import ensure_schema_upgrades

from tests.conftest import add_tx, login


# ---------------- 分类删除 ----------------
def test_delete_category_keeps_history(client, admin_headers, owner_headers, ids):
    tx = add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="expense",
                category_id=ids["mianfen"], amount="9.00", biz_date="2026-01-10")
    resp = client.delete(f"/api/categories/{ids['mianfen']}", headers=admin_headers)
    assert resp.status_code == 200

    # 列表中消失
    names = {c["name"] for c in client.get("/api/categories", headers=admin_headers).json()}
    assert "面粉/米面" not in names
    # 不能再用于新流水
    resp = client.post("/api/transactions", headers=owner_headers, json={
        "shop_id": ids["mianshi"], "type": "expense", "category_id": ids["mianfen"],
        "amount": "1.00", "payment_method": "cash", "biz_date": "2026-01-11"})
    assert resp.status_code == 400
    # 不能换入历史流水
    assert client.put(f"/api/transactions/{tx['id']}", headers=admin_headers,
                      json={"category_id": ids["mianfen"]}).status_code == 400
    # 历史流水的分类名与统计保留
    data = client.get("/api/transactions", headers=owner_headers).json()
    assert data["items"][0]["category_name"] == "面粉/米面"
    report = client.get("/api/reports/monthly?month=2026-01", headers=owner_headers).json()
    assert report["expense"] == "9.00"
    # 审计可查
    logs = client.get("/api/audit-logs?entity_type=category", headers=admin_headers).json()["items"]
    assert any(l["action"] == "delete" for l in logs)


def test_recreate_same_category_restores_record(client, admin_headers, ids):
    client.delete(f"/api/categories/{ids['mianfen']}", headers=admin_headers)
    resp = client.post("/api/categories", headers=admin_headers,
                       json={"type": "expense", "name": "面粉/米面"})
    assert resp.status_code == 201
    assert resp.json()["id"] == ids["mianfen"]  # 原记录恢复，历史流水自动接上


# ---------------- 店铺删除 ----------------
def test_delete_shop_keeps_history_and_protection(client, admin_headers, owner_headers, ids):
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
           category_id=ids["yingye"], amount="50.00", biz_date="2026-01-10")

    # 清掉其他测试可能创建的店铺，保证"最后一家"场景成立
    for s in client.get("/api/shops?include_disabled=1", headers=admin_headers).json():
        if s["id"] not in (ids["mianshi"], ids["zaocan"]):
            client.delete(f"/api/shops/{s['id']}", headers=admin_headers)

    resp = client.delete(f"/api/shops/{ids['zaocan']}", headers=admin_headers)
    assert resp.status_code == 200
    # 最后一个店铺不能删
    resp = client.delete(f"/api/shops/{ids['mianshi']}", headers=admin_headers)
    assert resp.status_code == 400
    assert "至少需要保留一个店铺" in resp.json()["detail"]

    shops = {s["name"] for s in client.get("/api/shops", headers=admin_headers).json()}
    assert "早餐店" not in shops and "面食店" in shops

    # 历史流水与分店铺统计保留店名
    data = client.get("/api/transactions", headers=owner_headers).json()
    assert data["items"][0]["shop_name"] == "面食店"
    report = client.get(f"/api/reports/range?start=2026-01-01&end=2026-01-31&shop_id={ids['mianshi']}",
                        headers=owner_headers).json()
    assert report["by_shop"][0]["shop_name"] == "面食店"

    # 同名重建恢复
    resp = client.post("/api/shops", headers=admin_headers, json={"name": "早餐店"})
    assert resp.status_code == 201 and resp.json()["id"] == ids["zaocan"]


# ---------------- 用户删除 ----------------
def test_delete_user_rules(client, admin_headers, owner_headers, ids):
    # 不能删自己
    me = client.get("/api/auth/me", headers=admin_headers).json()
    assert client.delete(f"/api/users/{me['id']}", headers=admin_headers).status_code == 400
    # 不能删最后一个 active admin（自己即最后一个，已被上一条覆盖；再造一个 admin 验证删除链）
    client.post("/api/users", headers=admin_headers,
                json={"username": "admin9", "password": "admin999", "role": "admin"})
    h9 = login(client, "admin9", "admin999")

    # 删除 owner：保留记录
    owner = client.get("/api/auth/me", headers=owner_headers).json()
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
           category_id=ids["yingye"], amount="66.00", biz_date="2026-01-10")
    assert client.delete(f"/api/users/{owner['id']}", headers=admin_headers).status_code == 200

    # 列表隐藏、无法登录（403 已删除）
    users = {u["username"] for u in client.get("/api/users", headers=admin_headers).json()}
    assert "owner" not in users
    resp = client.post("/api/auth/login", json={"username": "owner", "password": "owner123"})
    assert resp.status_code == 403
    assert "已被删除" in resp.json()["detail"]

    # 历史流水的创建人名字保留
    data = client.get("/api/transactions", headers=admin_headers).json()
    assert data["items"][0]["created_by_name"] == "owner"

    # 同名重建 = 恢复账号，用新密码可登录
    resp = client.post("/api/users", headers=admin_headers,
                       json={"username": "owner", "password": "newpass66", "role": "owner"})
    assert resp.status_code == 201 and resp.json()["id"] == owner["id"]
    assert client.post("/api/auth/login",
                       json={"username": "owner", "password": "newpass66"}).status_code == 200

    # admin9 删除 admin1（自己还在）→ 允许；再删自己 → 拒绝
    assert client.delete(f"/api/users/{me['id']}", headers=h9).status_code == 200
    me9 = client.get("/api/auth/me", headers=h9).json()
    resp = client.delete(f"/api/users/{me9['id']}", headers=h9)
    assert resp.status_code == 400


# ---------------- 旧库迁移 ----------------
def test_migration_adds_deleted_at_columns(tmp_path):
    """模拟 V1.1.1 之前的旧库结构：补列 + 旧数据保留 + 重复执行幂等。"""
    eng = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
        conn.exec_driver_sql("CREATE TABLE shops (id INTEGER PRIMARY KEY, name TEXT)")
        conn.exec_driver_sql("CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT)")
        conn.exec_driver_sql("INSERT INTO users (username) VALUES ('old_user')")
        conn.exec_driver_sql("INSERT INTO shops (name) VALUES ('老店')")
        conn.exec_driver_sql("INSERT INTO categories (name) VALUES ('旧分类')")

    ensure_schema_upgrades(eng)
    ensure_schema_upgrades(eng)  # 幂等

    with eng.connect() as conn:
        for table in ("users", "shops", "categories"):
            cols = {r[1] for r in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            assert "deleted_at" in cols
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM users").scalar() == 1
