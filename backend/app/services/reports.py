"""报表汇总：全部基于整数分计算，再转"元"字符串输出。"""
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Shop, Transaction
from ..utils import cents_to_yuan, profit_rate


def _base_query(db: Session, start: date, end: date, shop_id: int | None, shop_ids: list[int] | None = None):
    q = db.query(
        Transaction.type,
        Transaction.shop_id,
        func.sum(Transaction.amount_cents).label("total"),
    ).filter(
        Transaction.deleted_at.is_(None),
        Transaction.biz_date >= start,
        Transaction.biz_date <= end,
    )
    if shop_id is not None:
        q = q.filter(Transaction.shop_id == shop_id)
    if shop_ids is not None:
        q = q.filter(Transaction.shop_id.in_(shop_ids) if shop_ids else Transaction.shop_id == -1)
    return q


def summarize(
    db: Session, start: date, end: date, shop_id: int | None = None,
    shop_ids: list[int] | None = None,
) -> dict:
    """区间汇总：总收入、总支出、利润、利润率、分店铺明细、营业天数与日均。

    shop_ids：限定店铺范围（owner 的授权店铺）；None 表示全部。
    """
    rows = _base_query(db, start, end, shop_id, shop_ids).group_by(Transaction.type, Transaction.shop_id).all()

    # 营业日：当天存在至少一笔收入或支出流水
    days_q = db.query(func.count(func.distinct(Transaction.biz_date))).filter(
        Transaction.deleted_at.is_(None),
        Transaction.biz_date >= start,
        Transaction.biz_date <= end,
    )
    if shop_id is not None:
        days_q = days_q.filter(Transaction.shop_id == shop_id)
    if shop_ids is not None:
        days_q = days_q.filter(Transaction.shop_id.in_(shop_ids) if shop_ids else Transaction.shop_id == -1)
    business_days = int(days_q.scalar() or 0)

    income = 0
    expense = 0
    per_shop: dict[int, dict[str, int]] = {}

    for tx_type, sid, total in rows:
        total = int(total or 0)
        bucket = per_shop.setdefault(sid, {"income": 0, "expense": 0})
        if tx_type == "income":
            income += total
            bucket["income"] += total
        else:
            expense += total
            bucket["expense"] += total

    # 补齐店铺名（包括没有任何流水的活跃店铺？只列有流水的，保持简单）
    shop_names = {}
    if per_shop:
        ids = list(per_shop.keys())
        for s in db.query(Shop).filter(Shop.id.in_(ids)).all():
            shop_names[s.id] = s.name

    by_shop = [
        {
            "shop_id": sid,
            "shop_name": shop_names.get(sid, f"店铺{sid}"),
            "income": cents_to_yuan(v["income"]),
            "expense": cents_to_yuan(v["expense"]),
            "profit": cents_to_yuan(v["income"] - v["expense"]),
        }
        for sid, v in sorted(per_shop.items())
    ]

    profit = income - expense
    return {
        "start_date": start,
        "end_date": end,
        "income": cents_to_yuan(income),
        "expense": cents_to_yuan(expense),
        "profit": cents_to_yuan(profit),
        "profit_rate": profit_rate(profit, income),
        "by_shop": by_shop,
        "business_days": business_days,
        "avg_daily_income": cents_to_yuan(income // business_days) if business_days else None,
        "avg_daily_profit": cents_to_yuan(profit // business_days) if business_days else None,
    }


def expense_by_category(db: Session, start: date, end: date, shop_id: int | None = None,
                        shop_ids: list[int] | None = None) -> list[dict]:
    """区间内支出分类构成（含百分比），按金额降序。"""
    from ..models import Category

    q = db.query(
        Transaction.category_id,
        func.sum(Transaction.amount_cents).label("total"),
    ).filter(
        Transaction.deleted_at.is_(None),
        Transaction.type == "expense",
        Transaction.biz_date >= start,
        Transaction.biz_date <= end,
    )
    if shop_id is not None:
        q = q.filter(Transaction.shop_id == shop_id)
    if shop_ids is not None:
        q = q.filter(Transaction.shop_id.in_(shop_ids) if shop_ids else Transaction.shop_id == -1)
    rows = q.group_by(Transaction.category_id).all()

    names = {
        c.id: c.name
        for c in db.query(Category).filter(Category.id.in_([r[0] for r in rows])).all()
    } if rows else {}

    total = sum(int(r[1] or 0) for r in rows)
    result = []
    for cid, total_cents in rows:
        cents = int(total_cents or 0)
        pct = f"{cents / total * 100:.1f}%" if total > 0 else None
        result.append(
            {
                "category_id": cid,
                "category_name": names.get(cid, f"分类{cid}"),
                "amount": cents_to_yuan(cents),
                "percentage": pct,
                "_cents": cents,
            }
        )
    result.sort(key=lambda x: -x["_cents"])
    for item in result:
        del item["_cents"]
    return result


def daily_trend(db: Session, start: date, end: date, shop_id: int | None = None,
                shop_ids: list[int] | None = None) -> list[dict]:
    """逐日收入/支出/利润（含无流水的日期，补 0）。"""
    q = db.query(
        Transaction.biz_date,
        Transaction.type,
        func.sum(Transaction.amount_cents).label("total"),
    ).filter(
        Transaction.deleted_at.is_(None),
        Transaction.biz_date >= start,
        Transaction.biz_date <= end,
    )
    if shop_id is not None:
        q = q.filter(Transaction.shop_id == shop_id)
    if shop_ids is not None:
        q = q.filter(Transaction.shop_id.in_(shop_ids) if shop_ids else Transaction.shop_id == -1)
    rows = q.group_by(Transaction.biz_date, Transaction.type).all()

    data: dict[date, dict[str, int]] = {
        start + timedelta(days=i): {"income": 0, "expense": 0}
        for i in range((end - start).days + 1)
    }
    for d, tx_type, total in rows:
        bucket = data.setdefault(d, {"income": 0, "expense": 0})
        bucket["income" if tx_type == "income" else "expense"] += int(total or 0)

    return [
        {
            "date": d,
            "income": cents_to_yuan(v["income"]),
            "expense": cents_to_yuan(v["expense"]),
            "profit": cents_to_yuan(v["income"] - v["expense"]),
        }
        for d, v in sorted(data.items())
    ]
