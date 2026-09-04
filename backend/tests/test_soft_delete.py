"""软删除、恢复、管理员编辑与审计日志追溯测试。"""

from tests.conftest import add_tx


def make_one_tx(client, owner_headers, ids) -> dict:
    return add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
                  category_id=ids["yingye"], amount="100.00", biz_date="2026-01-10", remark="测试流水")


def test_owner_cannot_delete(client, owner_headers, ids):
    tx = make_one_tx(client, owner_headers, ids)
    resp = client.delete(f"/api/transactions/{tx['id']}", headers=owner_headers)
    assert resp.status_code == 403


def test_owner_cannot_update(client, owner_headers, ids):
    tx = make_one_tx(client, owner_headers, ids)
    resp = client.put(f"/api/transactions/{tx['id']}", headers=owner_headers, json={"amount": "999.00"})
    assert resp.status_code == 403


def test_soft_delete_excluded_from_list_and_reports(client, owner_headers, admin_headers, ids):
    tx = make_one_tx(client, owner_headers, ids)
    resp = client.delete(f"/api/transactions/{tx['id']}", headers=admin_headers)
    assert resp.status_code == 200

    data = client.get("/api/transactions", headers=owner_headers).json()
    assert data["total"] == 0
    reports = client.get("/api/reports/monthly?month=2026-01", headers=owner_headers).json()
    assert reports["income"] == "0.00"

    # 回收站可见（仅管理员）
    data = client.get("/api/transactions?include_deleted=1", headers=admin_headers).json()
    assert data["total"] == 1
    assert data["items"][0]["deleted_at"] is not None
    assert client.get("/api/transactions?include_deleted=1", headers=owner_headers).status_code == 403


def test_restore_deleted_transaction(client, owner_headers, admin_headers, ids):
    tx = make_one_tx(client, owner_headers, ids)
    client.delete(f"/api/transactions/{tx['id']}", headers=admin_headers)
    resp = client.post(f"/api/transactions/{tx['id']}/restore", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted_at"] is None

    data = client.get("/api/transactions", headers=owner_headers).json()
    assert data["total"] == 1
    reports = client.get("/api/reports/monthly?month=2026-01", headers=owner_headers).json()
    assert reports["income"] == "100.00"


def test_admin_update_writes_audit_before_after(client, owner_headers, admin_headers, ids):
    tx = make_one_tx(client, owner_headers, ids)
    resp = client.put(
        f"/api/transactions/{tx['id']}", headers=admin_headers,
        json={"amount": "150.00", "remark": "改过的备注"},
    )
    assert resp.status_code == 200
    assert resp.json()["amount"] == "150.00"

    logs = client.get("/api/audit-logs?entity_type=transaction", headers=admin_headers).json()["items"]
    actions = [log["action"] for log in logs]
    assert "create" in actions and "update" in actions
    update_log = next(l for l in logs if l["action"] == "update")
    assert update_log["before_data"]["amount"] == "100.00"
    assert update_log["after_data"]["amount"] == "150.00"
    assert update_log["username"] == "admin"


def test_delete_and_restore_audited(client, owner_headers, admin_headers, ids):
    tx = make_one_tx(client, owner_headers, ids)
    client.delete(f"/api/transactions/{tx['id']}", headers=admin_headers)
    client.post(f"/api/transactions/{tx['id']}/restore", headers=admin_headers)

    logs = client.get("/api/audit-logs?entity_type=transaction", headers=admin_headers).json()["items"]
    actions = [log["action"] for log in logs]
    assert actions.count("soft_delete") == 1
    assert actions.count("restore") == 1
    del_log = next(l for l in logs if l["action"] == "soft_delete")
    assert del_log["before_data"]["amount"] == "100.00"


def test_audit_logs_require_admin(client, owner_headers):
    assert client.get("/api/audit-logs", headers=owner_headers).status_code == 403
    assert client.get("/api/audit-logs").status_code == 401
