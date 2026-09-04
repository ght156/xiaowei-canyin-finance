"""金额工具：全程以"分"为单位的整数存储与计算，杜绝浮点误差。"""
from decimal import Decimal, InvalidOperation

# 最大金额 99,999,999.99 元
MAX_AMOUNT_CENTS = 9_999_999_999


class AmountError(ValueError):
    pass


def parse_amount_to_cents(value: str) -> int:
    """把"元"字符串（如 "12.50"）转为整数分。必须为正数且不超过上限。"""
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        raise AmountError("金额格式不正确")
    d = d.quantize(Decimal("0.01"))
    cents = int(d * 100)
    if cents <= 0:
        raise AmountError("金额必须大于0")
    if cents > MAX_AMOUNT_CENTS:
        raise AmountError("金额超出上限")
    return cents


def cents_to_yuan(cents: int) -> str:
    """整数分 → "元"字符串，保留两位小数。"""
    return f"{Decimal(cents) / Decimal(100):.2f}"


def profit_rate(profit_cents: int, income_cents: int) -> str | None:
    """利润率字符串（如 "35.6%"）；收入为 0 时返回 None（前端显示 —）。"""
    if income_cents <= 0:
        return None
    return f"{profit_cents / income_cents * 100:.1f}%"


PAYMENT_LABELS = {
    "cash": "现金",
    "wechat": "微信",
    "alipay": "支付宝",
    "card": "刷卡",
    "other": "其他",
}

TYPE_LABELS = {"income": "收入", "expense": "支出"}
