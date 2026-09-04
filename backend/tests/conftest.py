"""测试环境：临时数据库 + 种子数据 + TestClient。

注意：必须在导入 app 之前设置环境变量。
"""
import os
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="canyin_test_")
os.environ["APP_DB_PATH"] = str(Path(_TMP) / "test.db")
os.environ["APP_DATA_DIR"] = _TMP
os.environ["APP_SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from seed import seed  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def client():
    seed()
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_tables():
    """每个测试前清空流水/审计/备份记录，并把分类/店铺/用户恢复为种子状态，保证断言确定性。"""
    from sqlalchemy import delete, update

    from app.models import AuditLog, BackupRecord, Category, Shop, Transaction, User

    with SessionLocal() as db:
        db.execute(delete(Transaction))
        db.execute(delete(AuditLog))
        db.execute(delete(BackupRecord))
        db.execute(update(Category).values(status="active", deleted_at=None))
        db.execute(update(Shop).values(status="active", deleted_at=None))
        # 用户表恢复到种子状态（id 1=admin，2=owner），删除测试中新建的用户
        db.execute(delete(User).where(User.id > 2))
        db.execute(
            update(User).where(User.id == 1).values(role="admin", status="active", deleted_at=None)
        )
        db.execute(
            update(User).where(User.id == 2).values(role="owner", status="active", deleted_at=None)
        )
        db.commit()
    yield


def login(client: TestClient, username: str, password: str) -> dict:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin_headers(client):
    return login(client, "admin", "admin123")


@pytest.fixture(scope="session")
def owner_headers(client):
    return login(client, "owner", "owner123")


@pytest.fixture(scope="session")
def ids(client, admin_headers):
    """常用 id：店铺与分类。"""
    shops = {s["name"]: s["id"] for s in client.get("/api/shops", headers=admin_headers).json()}
    cats = client.get("/api/categories", headers=admin_headers).json()
    by_name = {c["name"]: c["id"] for c in cats}
    return {
        "mianshi": shops["面食店"],
        "zaocan": shops["早餐店"],
        "yingye": by_name["营业收入"],
        "qita_income": by_name["其他收入"],
        "mianfen": by_name["面粉/米面"],
        "fangzu": by_name["房租"],
    }


def add_tx(client: TestClient, headers: dict, *, shop_id: int, tx_type: str, category_id: int,
           amount: str, biz_date: str, payment_method: str = "cash", remark: str | None = None) -> dict:
    resp = client.post(
        "/api/transactions",
        headers=headers,
        json={
            "shop_id": shop_id,
            "type": tx_type,
            "category_id": category_id,
            "amount": amount,
            "payment_method": payment_method,
            "biz_date": biz_date,
            "remark": remark,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()
