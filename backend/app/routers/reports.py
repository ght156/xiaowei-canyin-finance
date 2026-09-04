"""经营统计：日 / 月 / 自定义区间 / 支出构成 / 首页总览。"""
import calendar
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Shop, User
from ..schemas import (
    DailyPoint,
    ExpenseCategoryItem,
    OverviewResponse,
    PeriodSummary,
    ReportSummary,
)
from ..security import get_current_user
from ..services import reports as svc

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _resolve_shop(db: Session, shop_id: int | None) -> tuple[int | None, str]:
    if shop_id is None:
        return None, "全部店铺"
    shop = db.get(Shop, shop_id)
    if shop is None:
        raise HTTPException(400, "店铺不存在")
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
    user: User = Depends(get_current_user),
):
    d = _parse_date(date, "date", default=datetime.now().date())
    sid, _ = _resolve_shop(db, shop_id)
    return svc.summarize(db, d, d, sid)


@router.get("/monthly", response_model=ReportSummary)
def monthly_report(
    month: str = Query(..., description="YYYY-MM"),
    shop_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        y, m = month.split("-")
        y, m = int(y), int(m)
        assert 1 <= m <= 12
    except (ValueError, AssertionError):
        raise HTTPException(422, "month 格式应为 YYYY-MM")
    start = date(y, m, 1)
    end = date(y, m, calendar.monthrange(y, m)[1])
    sid, _ = _resolve_shop(db, shop_id)
    return svc.summarize(db, start, end, sid)


@router.get("/range", response_model=ReportSummary)
def range_report(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    shop_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = _parse_date(start, "start")
    e = _parse_date(end, "end")
    if s > e:
        raise HTTPException(422, "开始日期不能晚于结束日期")
    sid, _ = _resolve_shop(db, shop_id)
    return svc.summarize(db, s, e, sid)


@router.get("/expense-categories", response_model=list[ExpenseCategoryItem])
def expense_categories(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    shop_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = _parse_date(start, "start")
    e = _parse_date(end, "end")
    if s > e:
        raise HTTPException(422, "开始日期不能晚于结束日期")
    sid, _ = _resolve_shop(db, shop_id)
    return svc.expense_by_category(db, s, e, sid)


@router.get("/trend", response_model=list[DailyPoint])
def trend_report(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    shop_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """逐日收入/支出/利润趋势（含无流水日期补 0）。"""
    s = _parse_date(start, "start")
    e = _parse_date(end, "end")
    if s > e:
        raise HTTPException(422, "开始日期不能晚于结束日期")
    sid, _ = _resolve_shop(db, shop_id)
    return svc.daily_trend(db, s, e, sid)


@router.get("/overview", response_model=OverviewResponse)
def overview(
    shop_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """首页数据：今日、本月、最近 7 天趋势，一次请求全部返回。"""
    today = datetime.now().date()
    month_start = today.replace(day=1)
    sid, shop_name = _resolve_shop(db, shop_id)

    today_sum = svc.summarize(db, today, today, sid)
    month_sum = svc.summarize(db, month_start, today, sid)
    trend = svc.daily_trend(db, today - timedelta(days=6), today, sid)

    def period(d: dict) -> PeriodSummary:
        return PeriodSummary(
            income=d["income"], expense=d["expense"],
            profit=d["profit"], profit_rate=d["profit_rate"],
        )

    return OverviewResponse(
        today=period(today_sum),
        month=period(month_sum),
        trend=[DailyPoint(**p) for p in trend],
        shop_id=sid,
        shop_name=shop_name,
    )
