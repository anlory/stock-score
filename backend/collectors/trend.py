import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as _date, timedelta
from sqlalchemy.orm import Session

from backend.collectors.tushare_client import get_pro, to_ts_code, to_ts_date, INDUSTRY_TS_CODE_MAP
from backend.database import upsert
from backend.models import Stock, DailyData

logger = logging.getLogger(__name__)
_MAX_WORKERS = 10


def _compute_returns(closes: list[float]) -> dict:
    out = {"return_5d": None, "return_20d": None, "return_60d": None}
    if not closes:
        return out
    today = closes[-1]
    for window, key in [(5, "return_5d"), (20, "return_20d"), (60, "return_60d")]:
        if len(closes) > window:
            past = closes[-window - 1]
            if past:
                out[key] = round((today - past) / past * 100, 2)
    return out


def _detect_patterns(d: dict, prev_macd_dif, prev_macd_dea) -> list[str]:
    tags = []
    ma5, ma13 = d.get("ma5"), d.get("ma13")
    pma5, pma13 = d.get("prev_ma5"), d.get("prev_ma13")
    if None not in (ma5, ma13, pma5, pma13):
        if ma5 > ma13 and pma5 < pma13:
            tags.append("MA5上穿MA13")
        elif ma5 < ma13 and pma5 > pma13:
            tags.append("MA5下穿MA13")
    vr, chg = d.get("volume_ratio"), d.get("change_pct")
    if vr is not None and chg is not None and vr > 2 and chg > 3:
        tags.append("放量上攻")
    dif, dea = d.get("macd_dif"), d.get("macd_dea")
    if None not in (dif, dea, prev_macd_dif, prev_macd_dea):
        if dif > dea and prev_macd_dif <= prev_macd_dea:
            tags.append("MACD金叉")
    return tags


def _fetch_closes(code: str, today: str) -> list[float]:
    pro = get_pro()
    start = to_ts_date((_date.fromisoformat(today) - timedelta(days=95)).isoformat())
    try:
        df = pro.daily(ts_code=to_ts_code(code), start_date=start, end_date=to_ts_date(today),
                       fields="ts_code,trade_date,close")
        if df is None or df.empty:
            return []
        return df.sort_values("trade_date")["close"].astype(float).tolist()
    except Exception as e:
        logger.warning(f"trend kline failed for {code}: {e}")
        return []


def _fetch_industry_changes(industry: str, today: str) -> dict:
    null = {"change": None, "change_5d": None, "change_20d": None}
    if not industry:
        return null
    ts_code = INDUSTRY_TS_CODE_MAP.get(industry)
    if not ts_code:
        return null
    pro = get_pro()
    start = to_ts_date((_date.fromisoformat(today) - timedelta(days=35)).isoformat())
    try:
        df = pro.ths_daily(ts_code=ts_code, start_date=start, end_date=to_ts_date(today),
                           fields="ts_code,trade_date,close")
        if df is None or df.empty or len(df) < 2:
            return null
        closes = df.sort_values("trade_date")["close"].astype(float).tolist()
        today_c = closes[-1]
        def _chg(n):
            return round((today_c - closes[-n - 1]) / closes[-n - 1] * 100, 2) if len(closes) > n and closes[-n - 1] else None
        return {"change": _chg(1), "change_5d": _chg(5), "change_20d": _chg(20)}
    except Exception as e:
        logger.warning(f"ths_daily failed for {industry}: {e}")
        return null


class _IndustryCache:
    def __init__(self, today: str):
        self._cache: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._today = today

    def get(self, industry: str) -> dict:
        if not industry:
            return {"change": None, "change_5d": None, "change_20d": None}
        with self._lock:
            if industry not in self._cache:
                self._cache[industry] = _fetch_industry_changes(industry, self._today)
            return self._cache[industry]


def _process_one(code, today, daily_dict, industry, industry_cache):
    closes = _fetch_closes(code, today)
    returns = _compute_returns(closes)
    ichanges = industry_cache.get(industry)
    tags = _detect_patterns(daily_dict, daily_dict.get("macd_dif"), daily_dict.get("macd_dea"))
    return {
        "code": code, "date": today,
        **returns,
        "industry_change": ichanges["change"],
        "industry_change_5d": ichanges["change_5d"],
        "industry_change_20d": ichanges["change_20d"],
        "pattern_tags": json.dumps(tags, ensure_ascii=False),
    }


def collect_trend(session: Session, target_codes: set[str], today: str | None = None) -> int:
    today = today or _date.today().isoformat()
    stocks = {s.code: s for s in session.query(Stock).filter(Stock.code.in_(target_codes))}
    dailies = session.query(DailyData).filter(DailyData.date == today, DailyData.code.in_(target_codes)).all()
    daily_map = {d.code: d for d in dailies}
    industry_cache = _IndustryCache(today)

    tasks = []
    for code in target_codes:
        daily = daily_map.get(code)
        if not daily:
            continue
        stock = stocks.get(code)
        industry = stock.industry if stock else None
        tasks.append((code, today, {k: v for k, v in daily.__dict__.items() if not k.startswith("_")}, industry, industry_cache))

    results = []
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_process_one, *task): task[0] for task in tasks}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                logger.error(f"Trend failed for {futures[future]}: {e}")

    count = 0
    for record in results:
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"Trend upsert failed for {record.get('code')}: {e}")

    session.commit()
    logger.info(f"Trend data collected: {count} stocks")
    return count
