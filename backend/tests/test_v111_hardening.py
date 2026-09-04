"""V1.1.1 加固测试：备份文件名唯一性、分类型保留、恢复管理员校验、
deleted_only 语义、非法参数 422、登录防爆破、生产环境 seed 保护。"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

import pytest

from app.config import BACKUP_DIR
from app.services import backup as backup_svc

from tests.conftest import add_tx, login


# ---------------- 备份文件名与保留策略 ----------------
def test_same_second_backups_have_unique_names(client, admin_headers):
    """同一秒内的两次备份文件名不得互相覆盖（微秒级时间戳）。"""
    a = client.post("/api/backups", headers=admin_headers).json()
    b = client.post("/api/backups", headers=admin_headers).json()
    assert a["file_name"] != b["file_name"]
    assert (BACKUP_DIR / a["file_name"]).exists()
    assert (BACKUP_DIR / b["file_name"]).exists()


def test_prune_quota_per_backup_type(client, admin_headers, monkeypatch):
    """手动备份再多，也不挤占 auto / pre_restore 各自的保留配额。"""
    monkeypatch.setattr(backup_svc, "BACKUP_KEEP", 2)
    monkeypatch.setattr(backup_svc, "PRE_RESTORE_KEEP", 1)
    for _ in range(4):
        client.post("/api/backups", headers=admin_headers)
    records = client.get("/api/backups", headers=admin_headers).json()
    assert len([r for r in records if r["backup_type"] == "manual"]) == 2


# ---------------- 恢复安全 ----------------
def test_restore_rejects_backup_without_active_admin(client, admin_headers, owner_headers, ids):
    """备份里没有启用中的管理员时必须拒绝恢复，否则恢复后无法登录管理。"""
    bad = BACKUP_DIR / "no_admin_backup.db"
    conn = sqlite3.connect(str(bad))
    try:
        for table in backup_svc.REQUIRED_TABLES:
            conn.execute(
                f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, name TEXT, role TEXT, status TEXT)"
            )
        conn.commit()
    finally:
        conn.close()
    try:
        add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
               category_id=ids["yingye"], amount="55.00", biz_date="2026-01-10")
        resp = client.post("/api/backups/no_admin_backup.db/restore", headers=admin_headers)
        assert resp.status_code == 400
        assert "管理员" in resp.json()["detail"]
        # 原库未受影响
        data = client.get("/api/transactions", headers=owner_headers).json()
        assert data["total"] == 1
    finally:
        bad.unlink(missing_ok=True)


# ---------------- deleted_only 语义 ----------------
def test_deleted_only_returns_only_deleted(client, admin_headers, owner_headers, ids):
    keep = add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
                  category_id=ids["yingye"], amount="10.00", biz_date="2026-01-10")
    gone = add_tx(client, owner_headers, shop_id=ids["mianshi"], tx_type="income",
                  category_id=ids["yingye"], amount="20.00", biz_date="2026-01-11")
    client.delete(f"/api/transactions/{gone['id']}", headers=admin_headers)

    recycle = client.get("/api/transactions?deleted_only=1", headers=admin_headers).json()
    assert recycle["total"] == 1
    assert recycle["items"][0]["id"] == gone["id"]

    normal = client.get("/api/transactions", headers=admin_headers).json()
    assert normal["total"] == 1
    assert normal["items"][0]["id"] == keep["id"]

    # 店主无权查看回收站
    assert client.get("/api/transactions?deleted_only=1", headers=owner_headers).status_code == 403


# ---------------- 非法参数 422 ----------------
def test_invalid_type_query_returns_422(client, admin_headers):
    assert client.get("/api/transactions?type=abc", headers=admin_headers).status_code == 422
    assert client.get("/api/categories?type=abc", headers=admin_headers).status_code == 422
    # 合法值不受影响
    assert client.get("/api/transactions?type=income", headers=admin_headers).status_code == 200
    assert client.get("/api/categories?type=expense", headers=admin_headers).status_code == 200


# ---------------- 登录防爆破（生产环境） ----------------
def test_login_rate_limit_in_production(client, monkeypatch):
    from app.routers import auth as auth_router

    monkeypatch.setattr(__import__("app.config", fromlist=["APP_ENV"]), "APP_ENV", "production")
    auth_router._login_failures.clear()
    try:
        for _ in range(5):
            resp = client.post("/api/auth/login",
                               json={"username": "admin", "password": "wrong"})
            assert resp.status_code == 401
        # 第 6 次：即使密码正确也被临时拒绝
        resp = client.post("/api/auth/login",
                           json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 429
        assert "5 分钟" in resp.json()["detail"]
    finally:
        auth_router._login_failures.clear()


def test_no_rate_limit_in_development(client):
    for _ in range(7):
        resp = client.post("/api/auth/login",
                           json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401  # 开发环境不限制尝试次数


# ---------------- 生产环境 seed 保护 ----------------
def _run_seed(env_extra: dict) -> subprocess.CompletedProcess:
    import tempfile

    env = os.environ.copy()
    env.update({
        "APP_ENV": "production",
        "APP_SECRET_KEY": "x" * 48,
        "APP_CORS_ORIGINS": "https://example.com",
        "APP_DB_PATH": str(Path(tempfile.mkdtemp(prefix="seed_test_")) / "seed.db"),
    })
    env.pop("SEED_ADMIN_PASSWORD", None)
    env.pop("SEED_OWNER_PASSWORD", None)
    env.update(env_extra)
    return subprocess.run([sys.executable, "seed.py"], capture_output=True, text=True,
                          cwd=str(BACKEND_DIR), env=env, timeout=120)


def test_seed_production_rejects_default_passwords():
    r = _run_seed({})
    assert r.returncode == 1
    assert "禁止创建默认弱密码" in r.stdout


def test_seed_production_accepts_env_passwords():
    r = _run_seed({"SEED_ADMIN_PASSWORD": "Str0ngAdmin!", "SEED_OWNER_PASSWORD": "Str0ngOwner!"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "密码来自环境变量" in r.stdout
