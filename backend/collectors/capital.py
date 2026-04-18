import logging
from datetime import date
import httpx
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_FF_URL = "http://push2.eastmoney.com/api/qt/stock/fflow/kline/get"


def _secid(code: str) -> str:
    if code.startswith(("6", "5", "9")):
        return f"1.{code}"
    if code.startswith(("4", "8")):
        return f"0.{code}"
    return f"0.{code}"


def collect_capital(session, target_codes: set[str] = None):
    """Fetch capital flow data per stock via eastmoney fund flow API."""
    today = date.today().isoformat()
    codes = sorted(target_codes) if target_codes else []
    if not codes:
        return 0

    count = 0
    for code in codes:
        try:
            secid = _secid(code)
            params = {
                "secid": secid,
                "fields1": "f1,f2,f3,f4",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
                "klt": "101",
                "lmt": "5",
            }
            r = httpx.get(_FF_URL, params=params, headers=_HEADERS, timeout=10, follow_redirects=True)
            r.raise_for_status()
            body = r.json()
            klines = body.get("data", {}).get("klines", [])
            if not klines:
                continue

            # Parse last row: date, main_inflow, small_inflow, medium_inflow, large_inflow, super_large_inflow
            last = klines[-1].split(",")
            if len(last) < 6:
                continue

            record = {
                "code": code, "date": today,
                "main_inflow_today": _parse_float(last[1]),
                "super_large_inflow": _parse_float(last[5]),
            }

            # 5-day main inflow sum
            if len(klines) >= 3:
                total = sum(_parse_float(k.split(",")[1]) for k in klines if len(k.split(",")) > 1)
                record["main_inflow_5d"] = round(total, 2)

            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"Capital failed for {code}: {e}")

    session.commit()
    logger.info(f"Capital data collected: {count} stocks")
    return count


def _parse_float(val: str):
    try:
        return round(float(val), 2)
    except (TypeError, ValueError):
        return None
