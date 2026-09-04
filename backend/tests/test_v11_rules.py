"""V1.1 规则测试：停用分类、管理员保护、生产配置、重复记账检测。"""
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

from tests.conftest import add_tx, login


# ---------------- 停用分类 ----------------
def test_disabled_category_rejected_for_new_tx(client, admin_headers, owner_headers, ids):
    client.put(f"/api/categories/{ids['mianfen']}", headers=admin_headers, json={"status": "disabled"})
    resp = client.post("/api/transactions", headers=owner_headers, json={
        "shop_id": ids["mianshi"], "type": "expense", "category_id": ids["mianfen"],
        "amount": "10.00", "payment_method": "cash", "biz_date": "2026-01-10",
    })
    assert resp.status_code == 400
    assert "停用" in resp.json()["detail"]


def test_cannot_switch_tx_to_disabled_category(client, admin_headers, owner_headers, ids):
    """管理员编辑流水时不能主动换到停用分类。"""
    tx = add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="expense",
                category_id=ids["mianfen"], amount="10.00", biz_date="2026-01-10")
    client.put(f"/api/categories/{ids['fangzu']}", headers=admin_headers, json={"status": "disabled"})
    resp = client.put(f"/api/transactions/{tx['id']}", headers=admin_headers,
                      json={"category_id": ids["fangzu"]})
    assert resp.status_code == 400
    # 历史数据未被破坏
    detail = client.get(f"/api/transactions/{tx['id']}", headers=admin_headers).json()
    assert detail["category_id"] == ids["mianfen"]


def test_edit_other_fields_keeps_disabled_category(client, admin_headers, owner_headers, ids):
    """原分类后来停用，编辑其他字段不受影响，历史数据保持完整。"""
    tx = add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="expense",
                category_id=ids["mianfen"], amount="10.00", biz_date="2026-01-10")
    client.put(f"/api/categories/{ids['mianfen']}", headers=admin_headers, json={"status": "disabled"})
    resp = client.put(f"/api/transactions/{tx['id']}", headers=admin_headers,
                      json={"remark": "改备注不改分类"})
    assert resp.status_code == 200
    assert resp.json()["category_id"] == ids["mianfen"]
    assert resp.json()["remark"] == "改备注不改分类"


def test_history_with_disabled_category_still_queryable(client, admin_headers, owner_headers, ids):
    """停用分类不能用于新业务，但历史流水（列表、报表、导出口径）不能消失。"""
    add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="expense",
           category_id=ids["mianfen"], amount="10.00", biz_date="2026-01-10")
    client.put(f"/api/categories/{ids['mianfen']}", headers=admin_headers, json={"status": "disabled"})

    data = client.get("/api/transactions", headers=owner_headers).json()
    assert data["total"] == 1
    assert data["items"][0]["category_name"] == "面粉/米面"

    report = client.get("/api/reports/monthly?month=2026-01", headers=owner_headers).json()
    assert report["expense"] == "10.00"


# ---------------- 管理员保护 ----------------
def test_cannot_demote_last_admin(client, admin_headers):
    me = client.get("/api/auth/me", headers=admin_headers).json()
    resp = client.put(f"/api/users/{me['id']}", headers=admin_headers, json={"role": "owner"})
    assert resp.status_code == 400
    assert "至少需要保留一个启用的管理员" in resp.json()["detail"]


def test_demote_allowed_when_another_admin_exists(client, admin_headers):
    client.post("/api/users", headers=admin_headers,
                json={"username": "admin2", "password": "admin222", "role": "admin"})
    h2 = login(client, "admin2", "admin222")

    me = client.get("/api/auth/me", headers=admin_headers).json()
    resp = client.put(f"/api/users/{me['id']}", headers=admin_headers, json={"role": "owner"})
    assert resp.status_code == 200  # 还有 admin2 在，可以降级

    # 现在 admin2 是最后一个管理员：不能自我降级、不能自我停用
    me2 = client.get("/api/auth/me", headers=h2).json()
    resp = client.put(f"/api/users/{me2['id']}", headers=h2, json={"role": "owner"})
    assert resp.status_code == 400
    resp = client.put(f"/api/users/{me2['id']}", headers=h2, json={"status": "disabled"})
    assert resp.status_code == 400


def test_admin_can_disable_another_admin_while_remaining(client, admin_headers):
    """存在其他 active admin 时，停用另一个管理员是允许的；保护规则只拦"最后一个"。"""
    client.post("/api/users", headers=admin_headers,
                json={"username": "admin3", "password": "admin333", "role": "admin"})
    h3 = login(client, "admin3", "admin333")

    # admin3 不能停用自己（自我保护）
    me3 = client.get("/api/auth/me", headers=h3).json()
    assert client.put(f"/api/users/{me3['id']}", headers=h3,
                      json={"status": "disabled"}).status_code == 400

    # admin1 仍是 active admin，停用 admin3 允许
    resp = client.put(f"/api/users/{me3['id']}", headers=admin_headers, json={"status": "disabled"})
    assert resp.status_code == 200


# ---------------- 生产环境配置 ----------------
def _run_config_env(env_extra: dict) -> subprocess.CompletedProcess:
    code = (
        "import os\n"
        "for k, v in os.environ.items():\n"
        "    if k.startswith('APP_'):\n"
        "        os.environ.pop(k)\n"
        "os.environ['APP_ENV']='production'\n"
        "os.environ['APP_SECRET_KEY']=os.environ.get('TEST_SECRET','x'*48)\n"
        "os.environ['APP_CORS_ORIGINS']=os.environ.get('TEST_CORS','https://example.com')\n"
        "try:\n"
        "    import app.config\n"
        "except RuntimeError:\n"
        "    print('REJECTED')\n"
        "else:\n"
        "    print('ACCEPTED')\n"
    )
    env = {"SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""), "PATH": __import__("os").environ.get("PATH", ""), **env_extra}
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          cwd=str(BACKEND_DIR), env=env, timeout=60)


def test_production_rejects_missing_secret():
    r = _run_config_env({"TEST_SECRET": ""})
    assert r.returncode == 0 and "REJECTED" in r.stdout


def test_production_rejects_default_dev_secret():
    r = _run_config_env({"TEST_SECRET": "dev-secret-please-change-in-production"})
    assert r.returncode == 0 and "REJECTED" in r.stdout


def test_production_rejects_wildcard_cors():
    r = _run_config_env({"TEST_CORS": "*"})
    assert r.returncode == 0 and "REJECTED" in r.stdout


def test_production_accepts_proper_config():
    r = _run_config_env({})
    assert "ACCEPTED" in r.stdout


def test_development_allows_defaults():
    code = "import app.config; print('ACCEPTED')"
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       cwd=str(BACKEND_DIR), timeout=60)
    assert "ACCEPTED" in r.stdout


# ---------------- 重复记账检测 ----------------
def test_duplicate_tx_warning(client, owner_headers, ids):
    body = {
        "shop_id": ids["mianshi"], "type": "income", "category_id": ids["yingye"],
        "amount": "88.00", "payment_method": "cash", "biz_date": "2026-01-10",
    }
    first = client.post("/api/transactions", headers=owner_headers, json=body)
    assert first.status_code == 201 and first.json()["duplicate_warning"] is False

    second = client.post("/api/transactions", headers=owner_headers, json=body)
    assert second.status_code == 201  # 不硬性禁止
    assert second.json()["duplicate_warning"] is True


def test_same_amount_different_day_not_duplicate(client, owner_headers, ids):
    body1 = {
        "shop_id": ids["mianshi"], "type": "income", "category_id": ids["yingye"],
        "amount": "88.00", "payment_method": "cash", "biz_date": "2026-01-10",
    }
    body2 = dict(body1, biz_date="2026-01-11")
    client.post("/api/transactions", headers=owner_headers, json=body1)
    resp = client.post("/api/transactions", headers=owner_headers, json=body2)
    assert resp.json()["duplicate_warning"] is False
