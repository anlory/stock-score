# backend/collectors/fundamental.py
import logging
from datetime import date
from backend.collectors.tushare_client import get_pro, to_ts_code, to_ts_date
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)


def _latest_fina_period(year: int, month: int) -> str:
    if month <= 4:
        return f"{year - 1}0930"
    if month <= 8:
        return f"{year - 1}1231"
    if month <= 10:
        return f"{year}0630"
    return f"{year}0930"


def collect_fundamental(session, target_codes: set[str] = None) -> int:
    today = date.today()
    today_str = today.isoformat()
    today_ts = to_ts_date(today_str)
    period = _latest_fina_period(today.year, today.month)

    if not target_codes:
        return 0

    pro = get_pro()

    # PE / PB / market_cap from daily_basic (full market, one call)
    basic_df = pro.daily_basic(trade_date=today_ts, fields="ts_code,pe_ttm,pb,total_mv")
    basic_map: dict[str, dict] = {}
    if basic_df is not None and not basic_df.empty:
        for _, row in basic_df.iterrows():
            code = row["ts_code"].split(".")[0]
            if code in target_codes:
                basic_map[code] = {
                    "pe": _safe_float(row.get("pe_ttm")),
                    "pb": _safe_float(row.get("pb")),
                    "market_cap": round(_safe_float(row.get("total_mv"), 0) / 10000, 4),
                }

    # ROE / profit_growth_yoy from fina_indicator (per stock, tushare only accepts single ts_code)
    fina_map: dict[str, dict] = {}
    for code in sorted(target_codes):
        try:
            df = pro.fina_indicator(ts_code=to_ts_code(code), period=period, fields="ts_code,roe,netprofit_yoy")
            if df is None or df.empty:
                continue
            row = df.iloc[0]
            fina_map[code] = {
                "roe": _safe_float(row.get("roe")),
                "profit_growth_yoy": _safe_float(row.get("netprofit_yoy")),
            }
        except Exception as e:
            logger.error(f"fina_indicator failed for {code}: {e}")

    count = 0
    for code in target_codes:
        record: dict = {"code": code, "date": today_str}
        record.update(basic_map.get(code, {}))
        record.update(fina_map.get(code, {}))
        if len(record) <= 2:
            continue
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"Fundamental upsert failed for {code}: {e}")

    session.commit()
    logger.info(f"Fundamental data collected: {count} stocks")
    return count


def _safe_float(val, default=None):
    try:
        import math
        v = float(val)
        return None if math.isnan(v) else round(v, 4)
    except (TypeError, ValueError):
        return default
