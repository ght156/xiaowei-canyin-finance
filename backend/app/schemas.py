"""Pydantic 请求/响应模型。金额一律用"元"字符串传输（如 "12.50"）。"""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# 金额：最多 8 位整数 + 2 位小数，正数（0 和负数由后端进一步校验）
AMOUNT_PATTERN = r"^\d{1,8}(\.\d{1,2})?$"

PaymentMethod = Literal["cash", "wechat", "alipay", "card", "other"]
TxType = Literal["income", "expense"]


# ---------- 认证 ----------
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=100)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    status: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=100)
    role: Literal["admin", "owner"] = "owner"


class UserUpdate(BaseModel):
    password: Optional[str] = Field(default=None, min_length=6, max_length=100)
    role: Optional[Literal["admin", "owner"]] = None
    status: Optional[Literal["active", "disabled"]] = None


# ---------- 店铺 ----------
class ShopCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class ShopUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    status: Optional[Literal["active", "disabled"]] = None


class ShopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: str
    created_at: datetime


# ---------- 分类 ----------
class CategoryCreate(BaseModel):
    type: TxType
    name: str = Field(min_length=1, max_length=50)
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    sort_order: Optional[int] = None
    status: Optional[Literal["active", "disabled"]] = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    name: str
    sort_order: int
    status: str


# ---------- 流水 ----------
class TransactionCreate(BaseModel):
    shop_id: int
    type: TxType
    category_id: int
    amount: str = Field(pattern=AMOUNT_PATTERN, description="金额（元），如 12.50")
    payment_method: PaymentMethod
    biz_date: date
    remark: Optional[str] = Field(default=None, max_length=200)


class TransactionUpdate(BaseModel):
    category_id: Optional[int] = None
    amount: Optional[str] = Field(default=None, pattern=AMOUNT_PATTERN)
    payment_method: Optional[PaymentMethod] = None
    biz_date: Optional[date] = None
    remark: Optional[str] = Field(default=None, max_length=200)


class TransactionOut(BaseModel):
    id: int
    shop_id: int
    shop_name: str
    type: str
    category_id: int
    category_name: str
    amount: str
    payment_method: str
    biz_date: date
    remark: Optional[str]
    created_by: int
    created_by_name: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]


class PagedTransactions(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TransactionOut]


# ---------- 报表 ----------
class ShopSummary(BaseModel):
    shop_id: int
    shop_name: str
    income: str
    expense: str
    profit: str


class ReportSummary(BaseModel):
    start_date: date
    end_date: date
    income: str
    expense: str
    profit: str
    profit_rate: Optional[str]  # 收入为 0 时为 null（前端显示 —）
    by_shop: list[ShopSummary]


class DailyPoint(BaseModel):
    date: date
    income: str
    expense: str
    profit: str


class PeriodSummary(BaseModel):
    income: str
    expense: str
    profit: str
    profit_rate: Optional[str]


class OverviewResponse(BaseModel):
    today: PeriodSummary
    month: PeriodSummary
    trend: list[DailyPoint]  # 最近 7 天（含今天）
    shop_id: Optional[int]
    shop_name: str  # "全部店铺" 或具体店铺名


class ExpenseCategoryItem(BaseModel):
    category_id: int
    category_name: str
    amount: str
    percentage: Optional[str]  # 占比，如 "23.5%"
