"""认证：登录、当前用户信息。"""
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..models import User
from ..schemas import LoginRequest, TokenResponse, UserOut
from ..security import create_access_token, get_current_user, verify_password
from ..services.audit import log_action

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 登录防爆破：仅 APP_ENV=production 时启用。
# 按 "IP+用户名" 记录失败次数，5 分钟内失败 5 次后临时拒绝。
_FAIL_LIMIT = 5
_FAIL_WINDOW_SECONDS = 300
_login_failures: dict[str, deque[float]] = defaultdict(deque)


def _rate_limited(key: str) -> bool:
    if config.APP_ENV != "production":
        return False
    now = time.monotonic()
    dq = _login_failures[key]
    while dq and now - dq[0] > _FAIL_WINDOW_SECONDS:
        dq.popleft()
    return len(dq) >= _FAIL_LIMIT


def _record_failure(key: str) -> None:
    if config.APP_ENV == "production":
        _login_failures[key].append(time.monotonic())


def _clear_failures(key: str) -> None:
    _login_failures.pop(key, None)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    key = f"{client_ip}:{body.username}"
    if _rate_limited(key):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "尝试次数过多，请 5 分钟后再试",
        )

    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        _record_failure(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    if user.deleted_at is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "该账号已被删除")
    if user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用，请联系管理员")

    _clear_failures(key)
    log_action(db, user.id, "login", "user", user.id)
    db.commit()
    return TokenResponse(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    """JWT 无状态，前端删除本地令牌即可。"""
    return {"ok": True}
