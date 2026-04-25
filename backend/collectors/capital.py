# backend/collectors/capital.py
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from backend.collectors.tushare_client import get_pro, to_ts_code, to_ts_date
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)
_MAX_WORKERS = 10


def _fetch_5d_sum(pro, code: str, today_ts: str) -> float | None:
    iso = f"{today_ts[:4]}-{today_ts[4:6]}-{today_ts[6:]}"
    start_ts = to_ts_date((date.fromisoformat(iso) - timedelta(days=14)).isoformat())
    try:
        df = pro.moneyflow(ts_code=to_ts_code(code), start_date=start_ts, end_date=today_ts,
                           fields="ts_code,trade_date,net_mf_amount")
        if df is None or df.empty:
            return None
        df = df.sort_values("trade_date")
        last5 = df.tail(5)["net_mf_amount"]
        return round(float(last5.sum()), 2)
    except Exception as e:
        logger.error(f"Capital 5d failed for {code}: {e}")
        return None


def collect_capital(session, target_codes: set[str] = None) -> int:
    today = date.today().isoformat()
    today_ts = to_ts_date(today)

    if not target_codes:
        return 0

    pro = get_pro()

    # Today's full-market moneyflow
    today_df = pro.moneyflow(
        trade_date=today_ts,
        fields="ts_code,buy_lg_amount,buy_elg_amount,net_mf_amount"
    )
    today_map: dict[str, dict] = {}
    if today_df is not None and not today_df.empty:
        for _, row in today_df.iterrows():
            code = row["ts_code"].split(".")[0]
            if code in target_codes:
                lg = _sf(row.get("buy_lg_amount"), 0.0)
                elg = _sf(row.get("buy_elg_amount"), 0.0)
                today_map[code] = {
                    "main_inflow_today": round(lg + elg, 2),
                    "super_large_inflow": elg,
                }

    # 5-day cumulative per stock (concurrent)
    codes = sorted(target_codes)
    five_d_map: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_5d_sum, pro, code, today_ts): code for code in codes}
        for future in as_completed(futures):
            code = futures[future]
            val = future.result()
            if val is not None:
                five_d_map[code] = val

    count = 0
    for code in target_codes:
        record: dict = {"code": code, "date": today}
        record.update(today_map.get(code, {}))
        if code in five_d_map:
            record["main_inflow_5d"] = five_d_map[code]
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
