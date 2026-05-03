# backend/collectors/tushare_client.py
import logging
import threading
import time
from datetime import date, timedelta
import tushare as ts
from backend.config import TUSHARE_TOKEN

logger = logging.getLogger(__name__)

_ts_semaphore = threading.Semaphore(2)   # 并发上限 3，留 1 个余量
_ts_rate_lock = threading.Lock()
_ts_state = {"last_call": 0.0}
_TS_MIN_INTERVAL = 60.0 / 100           # 100 次/分钟，低于上限 120

_RATE_LIMIT_KEYWORDS = ("频率过高", "限制120次", "请稍后重试")


def _is_rate_limited(e: Exception) -> bool:
    return any(kw in str(e) for kw in _RATE_LIMIT_KEYWORDS)


def _seconds_to_next_minute() -> float:
    """Seconds remaining until the next whole minute, plus 2s buffer."""
    return 62.0 - (time.time() % 60)


def ts_call(fn, *args, **kwargs):
    """Rate-limited tushare call. Retries up to 3 times on rate limit errors."""
    for attempt in range(3):
        with _ts_rate_lock:
            now = time.time()
            wait = _TS_MIN_INTERVAL - (now - _ts_state["last_call"])
            if wait > 0:
                time.sleep(wait)
            _ts_state["last_call"] = time.time()

        rate_limited = False
        with _ts_semaphore:
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                if _is_rate_limited(e) and attempt < 2:
                    rate_limited = True
                else:
                    raise

        if rate_limited:
            wait_s = _seconds_to_next_minute()
            logger.warning(f"Rate limit hit, waiting {wait_s:.0f}s until next minute (retry {attempt + 1}/3)")
            time.sleep(wait_s)

    raise RuntimeError("ts_call: rate limit retries exhausted")

_pro = None

# Populated by universe.py during sync; used by trend.py
# Maps industry name (str) → THS index ts_code (str), e.g. "银行" → "885096.TI"
INDUSTRY_TS_CODE_MAP: dict[str, str] = {}


def get_pro():
    global _pro
    if _pro is None:
        ts.set_token(TUSHARE_TOKEN)
        _pro = ts.pro_api()
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


def get_last_trade_date(as_of: str = None) -> str | None:
    """Return the most recent trading day (YYYY-MM-DD) on or before as_of (default: today)."""
    as_of = as_of or date.today().isoformat()
    start = (date.fromisoformat(as_of) - timedelta(days=14)).isoformat()
    try:
        pro = get_pro()
        df = ts_call(pro.trade_cal,
            start_date=to_ts_date(start),
            end_date=to_ts_date(as_of),
            is_open="1",
            fields="cal_date",
        )
        if df is None or df.empty:
            return None
        last = df.sort_values("cal_date").iloc[-1]["cal_date"]
        return f"{last[:4]}-{last[4:6]}-{last[6:]}"
    except Exception as e:
        logger.warning(f"get_last_trade_date failed: {e}")
        return None
