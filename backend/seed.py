"""初始化数据库：建表 + 默认分类 + 两个店铺 + 测试账号。

用法（在 backend 目录下）：
    python seed.py          # 幂等：已存在的内容不会重复创建
    python seed.py --reset  # 删除现有数据库后重建（危险，会清空所有数据）

生产环境（APP_ENV=production）首次初始化时禁止默认弱密码，
必须通过环境变量提供密码：
    SEED_ADMIN_PASSWORD=xxx SEED_OWNER_PASSWORD=xxx python seed.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import APP_ENV  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Category, Shop, User  # noqa: E402
from app.security import hash_password  # noqa: E402

INCOME_CATEGORIES = [
    "营业收入",
    "其他收入",
]

EXPENSE_CATEGORIES = [
    "面粉/米面",
    "蔬菜",
    "肉类",
    "鸡蛋",
    "食用油",
    "调料",
    "包装袋/餐盒",
    "燃气",
    "水费",
    "电费",
    "房租",
    "人工工资",
    "设备采购/维修",
    "运输",
    "其他",
]

SHOPS = ["面食店", "早餐店"]


def seed() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        # 用户：生产环境首次初始化禁止默认弱密码
        has_users = db.query(User).first() is not None
        if not has_users:
            admin_pw = os.environ.get("SEED_ADMIN_PASSWORD")
            owner_pw = os.environ.get("SEED_OWNER_PASSWORD")
            if APP_ENV == "production" and (not admin_pw or not owner_pw):
                print(
                    "[拒绝] 生产环境禁止创建默认弱密码账号。"
                    "请设置环境变量 SEED_ADMIN_PASSWORD 和 SEED_OWNER_PASSWORD 后重新执行 seed.py"
                )
                sys.exit(1)
            accounts = [
                ("admin", admin_pw or "admin123", "admin"),
                ("owner", owner_pw or "owner123", "owner"),
            ]
            for username, password, role in accounts:
                db.add(User(username=username, password_hash=hash_password(password), role=role))
                if APP_ENV == "production":
                    print(f"[+] 创建用户 {username}（{role}，密码来自环境变量）")
                else:
                    print(f"[+] 创建用户 {username}（{role}，默认密码 {password}）")

        # 店铺
        for name in SHOPS:
            if db.query(Shop).filter(Shop.name == name).first() is None:
                db.add(Shop(name=name))
                print(f"[+] 创建店铺 {name}")

        # 分类
        for i, name in enumerate(INCOME_CATEGORIES):
            if db.query(Category).filter(Category.type == "income", Category.name == name).first() is None:
                db.add(Category(type="income", name=name, sort_order=i))
                print(f"[+] 创建收入分类 {name}")
        for i, name in enumerate(EXPENSE_CATEGORIES):
            if db.query(Category).filter(Category.type == "expense", Category.name == name).first() is None:
                db.add(Category(type="expense", name=name, sort_order=i))
                print(f"[+] 创建支出分类 {name}")

        db.commit()
    print("初始化完成。")


if __name__ == "__main__":
    if "--reset" in sys.argv:
        confirm = input("将删除现有数据库并重建，确认？(输入 yes 确认)：")
        if confirm.strip().lower() == "yes":
            from app.config import DB_PATH

            if DB_PATH.exists():
                DB_PATH.unlink()
                print("已删除旧数据库。")
            seed()
        else:
            print("已取消。")
    else:
        seed()
