import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import httpx
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_FF_URL = "http://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
_MAX_WORKERS = 10


def _secid(code: str) -> str:
    if code.startswith(("6", "5", "9")):
        return f"1.{code}"
    if code.startswith(("4", "8")):
        return f"0.{code}"
    return f"0.{code}"


def _fetch_one(code, today):
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
            return None

        last = klines[-1].split(",")
        if len(last) < 6:
            return None

        record = {
            "code": code, "date": today,
            "main_inflow_today": _parse_float(last[1]),
            "super_large_inflow": _parse_float(last[5]),
        }

        if len(klines) >= 3:
            total = sum(_parse_float(k.split(",")[1]) for k in klines if len(k.split(",")) > 1)
            record["main_inflow_5d"] = round(total, 2)

        return record
    except Exception as e:
        logger.error(f"Capital failed for {code}: {e}")
        return None


def collect_capital(session, target_codes: set[str] = None):
    today = date.today().isoformat()
    codes = sorted(target_codes) if target_codes else []
    if not codes:
        return 0

    results = []
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_one, code, today): code for code in codes}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    count = 0
    for record in results:
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"Capital upsert failed for {record.get('code')}: {e}")

    session.commit()
    logger.info(f"Capital data collected: {count} stocks")
    return count


def _parse_float(val: str):
    try:
        return round(float(val), 2)
    except (TypeError, ValueError):
        return None
