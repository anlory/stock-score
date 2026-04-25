# backend/collectors/tushare_client.py
import tushare as ts
from backend.config import TUSHARE_TOKEN, TUSHARE_URL

_pro = None

# Populated by universe.py during sync; used by trend.py
# Maps industry name (str) → THS index ts_code (str), e.g. "银行" → "885096.TI"
INDUSTRY_TS_CODE_MAP: dict[str, str] = {}


def get_pro():
    global _pro
    if _pro is None:
        _pro = ts.pro_api(TUSHARE_TOKEN)
        _pro._DataApi__token = TUSHARE_TOKEN
        _pro._DataApi__http_url = TUSHARE_URL
    return _pro


def to_ts_code(code: str) -> str:
    """'000001' → '000001.SZ'"""
    if code.startswith(("6", "5", "9")):
        return f"{code}.SH"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return f"{code}.SZ"


def from_ts_code(ts_code: str) -> str:
    """'000001.SZ' → '000001'"""
    return ts_code.split(".")[0]


def to_ts_date(iso_date: str) -> str:
    """'2024-01-01' → '20240101'"""
    return iso_date.replace("-", "")
