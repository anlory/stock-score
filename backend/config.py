from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR}/stock_score.db"

INDEX_CODES = ["000300", "000905", "399006"]

HOT_SECTOR_TOP_N = 10
HOT_SECTOR_STOCKS_PER = 5

COLLECT_HOUR = 16
COLLECT_MINUTE = 0
