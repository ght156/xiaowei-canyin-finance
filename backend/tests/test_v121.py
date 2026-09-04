"""V1.2.1 修复测试：最后管理员保护补漏、员工可见范围收紧。"""
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import Transaction

from tests.conftest import add_tx, login, make_user


def get_emp(client, admin_headers, ids, username="emp_v121", shop_ids=None):
    return make_user(client, admin_headers, username=username, password="emp12345",
                     role="employee",
                     shop_ids=shop_ids if shop_ids is not None else [ids["zaocan"]])


# ---------------- 1. 最后管理员保护补漏 ----------------
def test_last_admin_cannot_become_employee(client, admin_headers):
    me = client.get("/api/auth/me", headers=admin_headers).json()
    resp = client.put(f"/api/users/{me['id']}", headers=admin_headers, json={"role": "employee"})
    assert resp.status_code == 400
    assert "至少需要保留一个启用的管理员" in resp.json()["detail"]


def test_admin_demote_allowed_when_two_admins(client, admin_headers):
    client.post("/api/users", headers=admin_headers,
                json={"username": "admin_b", "password": "admin999", "role": "admin"})
    me = client.get("/api/auth/me", headers=admin_headers).json()
    resp = client.put(f"/api/users/{me['id']}", headers=admin_headers, json={"role": "employee"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "employee"


def test_last_admin_cannot_be_disabled(client, admin_headers):
    me = client.get("/api/auth/me", headers=admin_headers).json()
    # 自我停用先被"不能停用自己的账号"拦截；用第二个管理员停用最后一个的场景
    client.post("/api/users", headers=admin_headers,
                json={"username": "admin_c", "password": "admin999", "role": "admin"})
    h_c = login(client, "admin_c", "admin999")
    me_c = client.get("/api/auth/me", headers=h_c).json()
    # admin_c 停用 admin（此时有两个 admin）→ 允许；admin_c 成为唯一 admin
    me = client.get("/api/auth/me", headers=admin_headers).json()
    assert client.put(f"/api/users/{me['id']}", headers=h_c,
                      json={"status": "disabled"}).status_code == 200
    # 唯一 admin_c 不能被停用（自我保护）也不能降级为 employee（本轮补的洞）
    resp = client.put(f"/api/users/{me_c['id']}", headers=h_c, json={"role": "employee"})
    assert resp.status_code == 400
    assert "至少需要保留一个启用的管理员" in resp.json()["detail"]


# ---------------- 2. employee-summary 不再返回 expense ----------------
def test_employee_summary_has_no_expense(client, admin_headers, owner_headers, ids):
    emp = get_emp(client, admin_headers, ids)
    from datetime import date as _d
    today = _d.today().isoformat()
    add_tx(client, owner_headers, shop_id=ids["zaocan"], tx_type="income",
           category_id=ids["yingye"], amount="50.00", biz_date=today)
    add_tx(client, owner_headers, shop_id=ids["zaocan"], tx_type="expense",
           category_id=ids["mianfen"], amount="30.00", biz_date=today)

    data = client.get(f"/api/reports/employee-summary?shop_id={ids['zaocan']}", headers=emp).json()
    assert data["income"] == "50.00"  # 只算收入
    assert data["count"] == 1  # 笔数也只统计当日收入流水
    assert "expense" not in data
    assert "profit" not in data


# ---------------- 3. 员工流水可见范围收紧 ----------------
def test_employee_cannot_see_others_today_expense(client, admin_headers, owner_headers, ids):
    """老板当天录入的支出（工资/房租等）对员工不可见：列表和详情都拦截。"""
    from datetime import date as _d
    today = _d.today().isoformat()
    emp = get_emp(client, admin_headers, ids)
    boss_expense = add_tx(client, owner_headers, shop_id=ids["zaocan"], tx_type="expense",
                          category_id=ids["fangzu"], amount="3000.00", biz_date=today, remark="老板交房租")

    data = client.get(f"/api/transactions?shop_id={ids['zaocan']}", headers=emp).json()
    assert all(item["id"] != boss_expense["id"] for item in data["items"])
    resp = client.get(f"/api/transactions/{boss_expense['id']}", headers=emp)
    assert resp.status_code == 403
    assert "员工只能查看自己录入的流水与当天店铺收入" in resp.json()["detail"]


def test_employee_can_see_today_shop_income(client, admin_headers, owner_headers, ids):
    """员工可以看到授权店铺当天的收入流水（含老板录入的）。"""
    from datetime import date as _d
    today = _d.today().isoformat()
    emp = get_emp(client, admin_headers, ids)
    boss_income = add_tx(client, owner_headers, shop_id=ids["zaocan"], tx_type="income",
                         category_id=ids["yingye"], amount="200.00", biz_date=today, remark="早市收款")
    data = client.get(f"/api/transactions?shop_id={ids['zaocan']}", headers=emp).json()
    assert any(item["id"] == boss_income["id"] for item in data["items"])
    assert client.get(f"/api/transactions/{boss_income['id']}", headers=emp).status_code == 200


def test_employee_can_see_own_transactions(client, admin_headers, ids):
    """员工能看到自己录入的全部允许流水（含历史、含支出）。"""
    emp = get_emp(client, admin_headers, ids)
    own_old = add_tx(client, emp, shop_id=ids["zaocan"], tx_type="expense",
                     category_id=ids["mianfen"], amount="6.00", biz_date="2026-01-10", remark="自己记的旧支出")
    data = client.get("/api/transactions", headers=emp).json()
    assert any(item["id"] == own_old["id"] for item in data["items"])
    assert client.get(f"/api/transactions/{own_old['id']}", headers=emp).status_code == 200


def test_employee_cannot_bypass_via_shop_id(client, admin_headers, ids):
    """显式传未授权 shop_id 的任何查询都 403，不能绕过。"""
    emp = get_emp(client, admin_headers, ids)
    resp = client.get(f"/api/transactions?shop_id={ids['mianshi']}", headers=emp)
    assert resp.status_code == 403
    assert "你没有该店铺的操作权限" in resp.json()["detail"]


def test_owner_permissions_unaffected(client, admin_headers, owner_headers, ids):
    """owner 权限保持：记账、编辑、删除、恢复、报表、导出、备份全部可用。"""
    tx = add_tx(client, owner_headers, shop_id=ids["zaocan"], tx_type="income",
                category_id=ids["yingye"], amount="11.00", biz_date="2026-01-10")
    assert client.put(f"/api/transactions/{tx['id']}", headers=owner_headers,
                      json={"amount": "12.00"}).status_code == 200
    assert client.delete(f"/api/transactions/{tx['id']}", headers=owner_headers).status_code == 200
    assert client.post(f"/api/transactions/{tx['id']}/restore", headers=owner_headers).status_code == 200
    assert client.get("/api/reports/monthly?month=2026-01", headers=owner_headers).status_code == 200
    assert client.get("/api/export?start=2026-01-01&end=2026-01-31", headers=owner_headers).status_code == 200
    assert client.post("/api/backups", headers=owner_headers).status_code == 201
