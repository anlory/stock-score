import logging
from datetime import date
from backend.collectors.base import query_wencai, normalize_code
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)

HEAT_QUERY = (
    "股票代码,"
    "涨跌幅,换手率,量比,"
    "连续涨停天数,所属行业板块涨幅排名"
)

FIELD_MAP = {
    "change_pct":           ["涨跌幅"],
    "turnover_rate":        ["换手率"],
    "volume_ratio":         ["量比"],
    "consecutive_limit_up": ["连续涨停天数", "连板数"],
    "sector_heat_rank":     ["所属行业板块涨幅排名", "板块涨幅排名"],
}

def _find_col(df, candidates):
    return next((c for c in candidates if c in df.columns), None)

def collect_market_heat(session, target_codes: set[str] = None):
    today = date.today().isoformat()
    df = query_wencai(HEAT_QUERY)
    if df.empty:
        logger.warning("Market heat query returned empty")
        return 0

    code_col = _find_col(df, ["股票代码", "代码"])
    if not code_col:
        return 0

    count = 0
    for _, row in df.iterrows():
        code = normalize_code(row[code_col])
        if target_codes and code not in target_codes:
            continue
        record = {"code": code, "date": today}
        for field, candidates in FIELD_MAP.items():
            col = _find_col(df, candidates)
            val = row.get(col) if col else None
            if field in ("consecutive_limit_up", "sector_heat_rank"):
                try:
                    record[field] = int(val) if val is not None else 0
                except (TypeError, ValueError):
                    record[field] = 0
            else:
                try:
                    record[field] = float(val) if val is not None else None
                except (TypeError, ValueError):
                    record[field] = None
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"Heat upsert failed for {code}: {e}")

    session.commit()
    logger.info(f"Market heat data collected: {count} stocks")
    return count
