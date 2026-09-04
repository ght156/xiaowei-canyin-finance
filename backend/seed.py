"""初始化数据库：建表 + 默认分类 + 两个店铺 + 测试账号。

用法（在 backend 目录下）：
    python seed.py          # 幂等：已存在的内容不会重复创建
    python seed.py --reset  # 删除现有数据库后重建（危险，会清空所有数据）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

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

DEFAULT_USERS = [
    # (用户名, 密码, 角色) —— 部署后请立即修改默认密码
    ("admin", "admin123", "admin"),
    ("owner", "owner123", "owner"),
]


def seed() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        # 用户
        for username, password, role in DEFAULT_USERS:
            if db.query(User).filter(User.username == username).first() is None:
                db.add(User(username=username, password_hash=hash_password(password), role=role))
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
