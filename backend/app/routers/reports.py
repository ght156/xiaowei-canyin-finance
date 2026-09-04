"""经营统计：日 / 月 / 自定义区间 / 支出构成 / 首页总览 / 员工汇总。

权限：
- admin：全部店铺
- owner：仅授权店铺（越权 shop_id 返回 403）
- employee：仅 GET /employee-summary（当前店铺今日营业额与笔数，不含利润）
"""
import calendar
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Shop, Transaction, User
from ..permissions import authorized_shop_ids, ensure_shop_access, shop_ids_or_all
from ..schemas import (
    DailyPoint,
    ExpenseCategoryItem,
    OverviewResponse,
    PeriodSummary,
    ReportSummary,
)
from ..security import get_current_user
from ..services import reports as svc
from ..tz import today_cn
from ..utils import cents_to_yuan

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _require_viewer(user: User = Depends(get_current_user)) -> User:
    """经营分析仅 admin/owner 可用。"""
    if user.role == "employee":
        raise HTTPException(403, "员工账号无权查看经营分析")
    return user


def _resolve_shop(db: Session, user: User, shop_id: int | None) -> tuple[int | None, str]:
    """解析店铺参数：校验存在性与访问权限。返回 (shop_id, 店铺名)。"""
    if shop_id is None:
        if user.role == "admin":
            return None, "全部店铺"
        # owner：多个授权店铺显示"我的店铺"，单店显示店名
        allowed = authorized_shop_ids(db, user)
        if allowed and len(allowed) == 1:
            shop = db.get(Shop, allowed[0])
            return None, shop.name if shop else "我的店铺"
        return None, "我的店铺"
    shop = db.get(Shop, shop_id)
    if shop is None or shop.deleted_at is not None:
        raise HTTPException(400, "店铺不存在")
    ensure_shop_access(db, user, shop_id)
    return shop_id, shop.name


def _parse_date(value: str | None, field: str, default: date | None = None) -> date:
    if value is None:
        if default is None:
            raise HTTPException(422, f"缺少参数 {field}")
        return default
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(422, f"{field} 格式应为 YYYY-MM-DD")


@router.get("/daily", response_model=ReportSummary)
def daily_report(
    date: str | None = Query(None, description="YYYY-MM-DD，默认今天"),
    shop_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(_require_viewer),
):
    d = _parse_date(date, "date", default=today_cn())
    sid, _ = _resolve_shop(db, user, shop_id)
    return svc.summarize(db, d, d, sid, shop_ids_or_all(db, user))


@router.get("/monthly", response_model=ReportSummary)
def monthly_report(
    month: str = Query(..., description="YYYY-MM"),
    shop_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(_require_viewer),
):
    try:
        y, m = month.split("-")
        y, m = int(y), int(m)
        assert 1 <= m <= 12
    except (ValueError, AssertionError):
        raise HTTPException(422, "month 格式应为 YYYY-MM")
    start = date(y, m, 1)
    end = date(y, m, calendar.monthrange(y, m)[1])
    sid, _ = _resolve_shop(db, user, shop_id)
    return svc.summarize(db, start, end, sid, shop_ids_or_all(db, user))


@router.get("/range", response_model=ReportSummary)
def range_report(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    shop_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(_require_viewer),
):
    s = _parse_date(start, "start")
    e = _parse_date(end, "end")
    if s > e:
        raise HTTPException(422, "开始日期不能晚于结束日期")
    sid, _ = _resolve_shop(db, user, shop_id)
    return svc.summarize(db, s, e, sid, shop_ids_or_all(db, user))


@router.get("/expense-categories", response_model=list[ExpenseCategoryItem])
def expense_categories(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    shop_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(_require_viewer),
):
    s = _parse_date(start, "start")
    e = _parse_date(end, "end")
    if s > e:
        raise HTTPException(422, "开始日期不能晚于结束日期")
    sid, _ = _resolve_shop(db, user, shop_id)
    return svc.expense_by_category(db, s, e, sid, shop_ids_or_all(db, user))


@router.get("/trend", response_model=list[DailyPoint])
def trend_report(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    shop_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(_require_viewer),
):
    """逐日收入/支出/利润趋势（含无流水日期补 0）。"""
    s = _parse_date(start, "start")
    e = _parse_date(end, "end")
    if s > e:
        raise HTTPException(422, "开始日期不能晚于结束日期")
    sid, _ = _resolve_shop(db, user, shop_id)
    return svc.daily_trend(db, s, e, sid, shop_ids_or_all(db, user))


@router.get("/overview", response_model=OverviewResponse)
def overview(
    shop_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(_require_viewer),
):
    """首页数据：今日、昨日、本月、最近 7 天趋势，一次请求全部返回。"""
    today = today_cn()
    month_start = today.replace(day=1)
    sid, shop_name = _resolve_shop(db, user, shop_id)
    scope = shop_ids_or_all(db, user)

    today_sum = svc.summarize(db, today, today, sid, scope)
    yesterday_sum = svc.summarize(db, today - timedelta(days=1), today - timedelta(days=1), sid, scope)
    month_sum = svc.summarize(db, month_start, today, sid, scope)
    trend = svc.daily_trend(db, today - timedelta(days=6), today, sid, scope)

    def period(d: dict) -> PeriodSummary:
        return PeriodSummary(
            income=d["income"], expense=d["expense"],
            profit=d["profit"], profit_rate=d["profit_rate"],
        )

    return OverviewResponse(
        today=period(today_sum),
        yesterday=period(yesterday_sum),
        month=period(month_sum),
        trend=[DailyPoint(**p) for p in trend],
        shop_id=sid,
        shop_name=shop_name,
    )


@router.get("/employee-summary")
def employee_summary(
    shop_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """员工首页数据：当前店铺今日营业额与笔数。不返回利润、支出等经营敏感数据。"""
    if user.role != "employee":
        raise HTTPException(403, "该接口仅面向员工账号")

    allowed = authorized_shop_ids(db, user)
    if shop_id is not None:
        ensure_shop_access(db, user, shop_id)
        target = shop_id
    else:
        if not allowed:
            raise HTTPException(403, "你没有被授权任何店铺，请联系管理员")
        target = allowed[0]

    shop = db.get(Shop, target)
    today = today_cn()
    rows = db.query(
        func.count(Transaction.id).label("cnt"),
        func.sum(Transaction.amount_cents).label("total"),
    ).filter(
        Transaction.deleted_at.is_(None),
        Transaction.shop_id == target,
        Transaction.biz_date == today,
        Transaction.type == "income",
    ).one()

    return {
        "shop_id": target,
        "shop_name": shop.name if shop else f"店铺{target}",
        "date": today,
        "income": cents_to_yuan(int(rows.total or 0)),
        "count": int(rows.cnt or 0),
    }
