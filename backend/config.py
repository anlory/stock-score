import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

DATABASE_URL = f"sqlite:///{DATA_DIR}/stock_score.db"

INDEX_CODES = ["000300", "000905", "399006"]
HOT_SECTOR_TOP_N = 10
HOT_SECTOR_STOCKS_PER = 5
COLLECT_HOUR = 16
COLLECT_MINUTE = 0

# GLM AI config
AI_API_KEY = os.getenv("GLM_API_KEY", "")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://open.bigmodel.cn/api/coding/paas/v4")
AI_MODEL = os.getenv("AI_MODEL", "glm-5.1")

# Tushare
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
TUSHARE_URL = os.getenv("TUSHARE_URL", "http://jiaoch.site")

def ensure_dirs() -> None:
    DATA_DIR.mkdir(exist_ok=True)
