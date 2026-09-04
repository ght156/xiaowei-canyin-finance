"""数据库模型：users / shops / categories / transactions / audit_logs / backup_records"""
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .tz import naive_now


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="owner")  # admin=管理员 / owner=店主
    status: Mapped[str] = mapped_column(String(20), default="active")  # active / disabled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 软删除


class Shop(Base):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 软删除


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("type", "name", name="uq_category_type_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(10))  # income / expense
    name: Mapped[str] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 软删除


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_tx_shop_date", "shop_id", "biz_date"),
        Index("ix_tx_date", "biz_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"))
    type: Mapped[str] = mapped_column(String(10))  # income / expense
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    amount_cents: Mapped[int] = mapped_column(Integer)  # 金额，单位：分
    payment_method: Mapped[str] = mapped_column(String(20))  # cash/wechat/alipay/card/other
    biz_date: Mapped[date] = mapped_column(Date)
    remark: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=naive_now, onupdate=naive_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 软删除

    shop: Mapped["Shop"] = relationship()
    category: Mapped["Category"] = relationship()
    creator: Mapped["User"] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_created", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(30))  # create/update/soft_delete/restore/...
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    before_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_now)


class BackupRecord(Base):
    __tablename__ = "backup_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_name: Mapped[str] = mapped_column(String(100))
    backup_type: Mapped[str] = mapped_column(String(20), default="manual")  # manual / auto
    status: Mapped[str] = mapped_column(String(20), default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_now)
