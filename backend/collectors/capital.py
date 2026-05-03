# backend/collectors/capital.py
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from backend.collectors.tushare_client import get_pro, to_ts_code, to_ts_date, ts_call
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)
_MAX_WORKERS = 10


def _fetch_stock_flows(pro, code: str, today_ts: str) -> dict:
    """Fetch today's inflow and 5-day cumulative for one stock in a single API call."""
    iso = f"{today_ts[:4]}-{today_ts[4:6]}-{today_ts[6:]}"
    start_ts = to_ts_date((date.fromisoformat(iso) - timedelta(days=14)).isoformat())
    try:
        df = ts_call(pro.moneyflow,
            ts_code=to_ts_code(code), start_date=start_ts, end_date=today_ts,
            fields="ts_code,trade_date,buy_elg_amount,sell_elg_amount,net_mf_amount",
        )
        if df is None or df.empty:
            return {}
        df = df.sort_values("trade_date")
        result = {}
        today_row = df[df["trade_date"] == today_ts]
        if not today_row.empty:
            r = today_row.iloc[0]
            buy_elg = _sf(r.get("buy_elg_amount"), 0.0)
            sell_elg = _sf(r.get("sell_elg_amount"), 0.0)
            result["main_inflow_today"] = _sf(r.get("net_mf_amount"))
            result["super_large_inflow"] = round(buy_elg - sell_elg, 2)
        last5 = df.tail(5)["net_mf_amount"].dropna()
        if not last5.empty:
            result["main_inflow_5d"] = round(float(last5.sum()), 2)
        return result
    except Exception as e:
        logger.error(f"Capital flow failed for {code}: {e}")
        return {}


def collect_capital(session, target_codes: set[str] = None, today: str = None) -> int:
    today = today or date.today().isoformat()
    today_ts = to_ts_date(today)

    if not target_codes:
        return 0

    pro = get_pro()
    codes = sorted(target_codes)

    flow_map: dict[str, dict] = {}
    total = len(codes)
    done = 0
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_stock_flows, pro, code, today_ts): code for code in codes}
        for future in as_completed(futures):
            code = futures[future]
            result = future.result()
            if result:
                flow_map[code] = result
            done += 1
            if done % 50 == 0 or done == total:
                logger.info(f"Capital: {done}/{total}")

    count = 0
    for code in target_codes:
        flows = flow_map.get(code, {})
        if not flows:
            continue
        record: dict = {"code": code, "date": today, **flows}
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"Capital upsert failed for {code}: {e}")

    session.commit()
    logger.info(f"Capital data collected: {count} stocks")
    return count


def _sf(val, default=None):
    try:
        import math
        v = float(val)
        return default if math.isnan(v) else round(v, 2)
    except (TypeError, ValueError):
        return default
