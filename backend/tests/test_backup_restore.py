"""V1.1 备份与恢复强化测试：安全备份、校验、回滚、下载、每日自动备份。"""
from pathlib import Path

from app.config import BACKUP_DIR

from tests.conftest import add_tx


def test_auto_backup_triggered_by_first_tx(client, admin_headers, owner_headers, ids):
    """每天第一笔流水自动触发当日备份，不依赖应用重启。"""
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
           category_id=ids["yingye"], amount="10.00", biz_date="2026-01-10")
    records = client.get("/api/backups", headers=admin_headers).json()
    autos = [r for r in records if r["backup_type"] == "auto"]
    assert len(autos) == 1


def test_second_tx_same_day_no_extra_auto_backup(client, admin_headers, owner_headers, ids):
    body = lambda amount: {
        "shop_id": ids["mianshi"], "type": "income", "category_id": ids["yingye"],
        "amount": amount, "payment_method": "cash", "biz_date": "2026-01-10",
    }
    client.post("/api/transactions", headers=owner_headers, json=body("10.00"))
    client.post("/api/transactions", headers=owner_headers, json=body("20.00"))
    records = client.get("/api/backups", headers=admin_headers).json()
    assert len([r for r in records if r["backup_type"] == "auto"]) == 1


def test_restore_missing_backup_fails_db_intact(client, admin_headers, owner_headers, ids):
    tx = add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
                category_id=ids["yingye"], amount="111.00", biz_date="2026-01-10")
    resp = client.post("/api/backups/no_such_backup.db/restore", headers=admin_headers)
    assert resp.status_code == 400
    data = client.get("/api/transactions", headers=owner_headers).json()
    assert data["total"] == 1 and data["items"][0]["amount"] == "111.00"


def test_restore_corrupt_backup_fails_db_intact(client, admin_headers, owner_headers, ids):
    bad = BACKUP_DIR / "corrupt_backup.db"
    bad.write_text("this is not a sqlite database", encoding="utf-8")
    try:
        add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
               category_id=ids["yingye"], amount="222.00", biz_date="2026-01-10")
        resp = client.post("/api/backups/corrupt_backup.db/restore", headers=admin_headers)
        assert resp.status_code == 400
        assert "SQLite" in resp.json()["detail"]
        data = client.get("/api/transactions", headers=owner_headers).json()
        assert data["total"] == 1 and data["items"][0]["amount"] == "222.00"
    finally:
        bad.unlink(missing_ok=True)


def test_restore_success_reverts_data_and_keeps_safety_record(client, admin_headers, owner_headers, ids):
    """恢复成功：数据回到备份点；恢复前安全备份（文件+记录）可追溯。"""
    tx_a = add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
                  category_id=ids["yingye"], amount="77.00", biz_date="2026-01-10", remark="A")
    backup = client.post("/api/backups", headers=admin_headers).json()
    file_name = backup["file_name"]

    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="expense",
           category_id=ids["mianfen"], amount="88.00", biz_date="2026-01-11", remark="B")

    resp = client.post(f"/api/backups/{file_name}/restore", headers=admin_headers)
    assert resp.status_code == 200

    # 数据回到备份时间点：A 在，B 不在
    amounts = {t["remark"]: t["amount"] for t in client.get(
        "/api/transactions", headers=owner_headers).json()["items"]}
    assert amounts == {"A": "77.00"}

    # 安全备份记录与文件可追溯
    records = client.get("/api/backups", headers=admin_headers).json()
    pre = [r for r in records if r["backup_type"] == "pre_restore"]
    assert len(pre) == 1
    assert (BACKUP_DIR / pre[0]["file_name"]).exists()


def test_backup_download(client, admin_headers, owner_headers):
    created = client.post("/api/backups", headers=admin_headers).json()
    resp = client.get(f"/api/backups/{created['file_name']}/download", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.content.startswith(b"SQLite format 3\x00")

    assert client.get("/api/backups/no_such.db/download", headers=admin_headers).status_code == 404
    assert client.get(f"/api/backups/{created['file_name']}/download",
                      headers=owner_headers).status_code == 403
