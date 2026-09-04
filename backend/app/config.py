"""全局配置：数据库路径、密钥、备份目录等，支持 .env 与环境变量覆盖。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/

# 可选加载 backend/.env（不覆盖已存在的环境变量）
_env_path = BASE_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

APP_NAME = "小微餐饮财务管理系统"

DATA_DIR = Path(os.environ.get("APP_DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.environ.get("APP_DB_PATH", str(DATA_DIR / "app.db")))
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

# 生产部署务必在 .env 中设置随机长密钥
SECRET_KEY = os.environ.get("APP_SECRET_KEY", "dev-secret-please-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = int(os.environ.get("APP_TOKEN_EXPIRE_DAYS", "7"))

BACKUP_DIR = Path(os.environ.get("APP_BACKUP_DIR", str(DATA_DIR / "backups")))
BACKUP_KEEP = int(os.environ.get("APP_BACKUP_KEEP", "30"))

_cors = os.environ.get("APP_CORS_ORIGINS", "*")
CORS_ORIGINS = [o.strip() for o in _cors.split(",") if o.strip()]

# development：允许宽松默认值；production：强制安全配置
APP_ENV = os.environ.get("APP_ENV", "development")

_DEV_SECRET = "dev-secret-please-change-in-production"


def check_production_security() -> None:
    """生产环境启动前强制安全检查，不满足则拒绝启动。"""
    if APP_ENV != "production":
        return
    if not SECRET_KEY or SECRET_KEY == _DEV_SECRET:
        raise RuntimeError(
            "生产环境安全检查失败：必须设置随机 APP_SECRET_KEY。"
            "生成方法：python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    if "*" in CORS_ORIGINS:
        raise RuntimeError(
            "生产环境安全检查失败：APP_CORS_ORIGINS 不能为 *，请限定为实际前端域名。"
        )


check_production_security()
