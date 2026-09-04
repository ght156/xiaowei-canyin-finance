"""FastAPI 入口。"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import APP_NAME, CORS_ORIGINS
from .database import Base, SessionLocal, engine
from .migrations import ensure_schema_upgrades
from .routers import auth, categories, reports, shops, system, transactions
from .services.backup import maybe_auto_backup


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    ensure_schema_upgrades()  # 旧库补齐新增列，升级不丢数据
    # 每天首次启动自动备份一次
    with SessionLocal() as db:
        maybe_auto_backup(db)
    yield


app = FastAPI(title=APP_NAME, version="1.1.2", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(shops.router)
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(reports.router)
app.include_router(system.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": APP_NAME}


# 生产模式：若存在前端构建产物，则由后端直接托管（手机访问 http://<电脑IP>:8000 即可）
_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
