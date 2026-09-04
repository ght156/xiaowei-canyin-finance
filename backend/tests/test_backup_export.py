"""备份与 CSV 导出、用户管理测试。"""
from pathlib import Path

from app.config import BACKUP_DIR

from tests.conftest import add_tx, make_user


def test_backup_create_and_list(client, admin_headers):
    resp = client.post("/api/backups", headers=admin_headers)
    assert resp.status_code == 201
    file_name = resp.json()["file_name"]
    assert (BACKUP_DIR / file_name).exists()

    records = client.get("/api/backups", headers=admin_headers).json()
    assert any(r["file_name"] == file_name for r in records)


def test_backup_permission_by_role(client, admin_headers, owner_headers):
    """V1.2：owner 可手动备份；employee 无权。"""
    assert client.post("/api/backups", headers=owner_headers).status_code == 201
    emp = make_user(client, admin_headers, username="emp_bk", password="emp12345",
                    role="employee", shop_ids=[1])
    assert client.post("/api/backups", headers=emp).status_code == 403


def test_export_csv(client, admin_headers, owner_headers, ids):
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
           category_id=ids["yingye"], amount="88.50", biz_date="2026-01-15", remark="面条")
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="expense",
           category_id=ids["mianfen"], amount="12.00", biz_date="2026-01-16", remark="高筋粉")

    resp = client.get("/api/export?start=2026-01-01&end=2026-01-31", headers=admin_headers)
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    text = resp.content.decode("utf-8-sig")  # 自动去 BOM
    lines = [l for l in text.splitlines() if l]
    assert lines[0].startswith("日期,店铺,类型,分类,金额(元)")
    assert "2026-01-15,面食店,收入,营业收入,88.50,现金,面条,owner" in lines[1]
    assert any("支出" in l and "12.00" in l for l in lines[1:])


def test_export_permission_by_role(client, admin_headers, owner_headers, ids):
    """V1.2：owner 可导出（授权店铺范围）；employee 无权。"""
    resp = client.get("/api/export?start=2026-01-01&end=2026-01-31", headers=owner_headers)
    assert resp.status_code == 200
    emp = make_user(client, admin_headers, username="exp_emp", password="emp12345",
                    role="employee", shop_ids=[ids["zaocan"]])
    assert client.get("/api/export?start=2026-01-01&end=2026-01-31", headers=emp).status_code == 403


def test_export_deleted_excluded(client, admin_headers, owner_headers, ids):
    tx = add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
                category_id=ids["yingye"], amount="66.00", biz_date="2026-01-15")
    client.delete(f"/api/transactions/{tx['id']}", headers=admin_headers)
    resp = client.get("/api/export?start=2026-01-01&end=2026-01-31", headers=admin_headers)
    text = resp.content.decode("utf-8-sig")
    assert "66.00" not in text


def test_user_management(client, admin_headers, owner_headers):
    resp = client.post("/api/users", headers=admin_headers,
                       json={"username": "mama", "password": "mama123", "role": "owner"})
    assert resp.status_code == 201

    dup = client.post("/api/users", headers=admin_headers,
                      json={"username": "mama", "password": "mama123", "role": "owner"})
    assert dup.status_code == 400

    # 新用户能登录
    login_resp = client.post("/api/auth/login", json={"username": "mama", "password": "mama123"})
    assert login_resp.status_code == 200

    # 停用后无法登录
    uid = resp.json()["id"]
    client.put(f"/api/users/{uid}", headers=admin_headers, json={"status": "disabled"})
    login_resp = client.post("/api/auth/login", json={"username": "mama", "password": "mama123"})
    assert login_resp.status_code == 403

    # 不能停用自己
    me = client.get("/api/auth/me", headers=admin_headers).json()
    resp = client.put(f"/api/users/{me['id']}", headers=admin_headers, json={"status": "disabled"})
    assert resp.status_code == 400

    # 店主无权管理用户
    assert client.get("/api/users", headers=owner_headers).status_code == 403
