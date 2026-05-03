import logging
from datetime import date, timedelta
from backend.collectors.tushare_client import get_pro, to_ts_date, ts_call
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)


def _get_recent_trade_dates(pro, today_ts: str, n: int = 10) -> list[str]:
    y, m, d = today_ts[:4], today_ts[4:6], today_ts[6:]
    iso = f"{y}-{m}-{d}"
    start_ts = to_ts_date((date.fromisoformat(iso) - timedelta(days=20)).isoformat())
    cal = ts_call(pro.trade_cal, start_date=start_ts, end_date=today_ts, is_open="1")
    if cal is None or cal.empty:
        return [today_ts]
    dates = sorted(cal["cal_date"].tolist())
    return dates[-n:]


def collect_market_heat(session, target_codes: set[str] = None, today: str = None) -> int:
    today_str = today or date.today().isoformat()
    today_ts = to_ts_date(today_str)

    if not target_codes:
        return 0

    pro = get_pro()

    # change_pct from daily
    daily_df = ts_call(pro.daily, trade_date=today_ts, fields="ts_code,pct_chg,vol")
    daily_map: dict[str, float] = {}
    if daily_df is not None and not daily_df.empty:
        for _, row in daily_df.iterrows():
            code = row["ts_code"].split(".")[0]
            if code in target_codes:
                daily_map[code] = _sf(row.get("pct_chg"))

    # turnover_rate, volume_ratio from daily_basic
    basic_df = ts_call(pro.daily_basic, trade_date=today_ts, fields="ts_code,turnover_rate,volume_ratio")
    basic_map: dict[str, dict] = {}
    if basic_df is not None and not basic_df.empty:
        for _, row in basic_df.iterrows():
            code = row["ts_code"].split(".")[0]
            if code in target_codes:
                basic_map[code] = {
                    "turnover_rate": _sf(row.get("turnover_rate")),
                    "volume_ratio": _sf(row.get("volume_ratio")),
                }

    # consecutive_limit_up: query last 10 trading days
    trade_dates = _get_recent_trade_dates(pro, today_ts, n=10)
    limit_sets: list[set[str]] = []
    for td in reversed(trade_dates):  # newest first
        try:
            df = ts_call(pro.limit_list_d, trade_date=td, fields="ts_code,trade_date")
            if df is not None and not df.empty:
                limit_sets.append(set(r.split(".")[0] for r in df["ts_code"].tolist()))
            else:
                limit_sets.append(set())
        except Exception as e:
            logger.warning(f"limit_list_d failed for {td}: {e}")
            limit_sets.append(set())

    def _consecutive(code: str) -> int:
        count = 0
        for s in limit_sets:
            if code in s:
                count += 1
            else:
                break
        return count

    count = 0
    for code in target_codes:
        record: dict = {"code": code, "date": today_str}
        if code in daily_map:
            record["change_pct"] = daily_map[code]
        record.update(basic_map.get(code, {}))
        record["consecutive_limit_up"] = _consecutive(code)
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"Heat upsert failed for {code}: {e}")

    session.commit()
    logger.info(f"Market heat data collected: {count} stocks")
    return count


def _sf(val, default=None):
    try:
        import math
        v = float(val)
        return None if math.isnan(v) else round(v, 4)
    except (TypeError, ValueError):
        return default
