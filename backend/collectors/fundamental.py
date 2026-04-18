import logging
from datetime import date
from backend.collectors.base import query_wencai, normalize_code
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)

FUNDAMENTAL_QUERY = (
    "股票代码,"
    "市盈率(动),市净率,ROE,"
    "净利润同比增长率,总市值"
)

FIELD_MAP = {
    "pe":                ["市盈率(动)", "市盈率", "PE"],
    "pb":                ["市净率", "PB"],
    "roe":               ["ROE"],
    "profit_growth_yoy": ["净利润同比增长率", "净利润增长率"],
    "market_cap":        ["总市值"],
}

def _find_col(df, candidates):
    return next((c for c in candidates if c in df.columns), None)

def collect_fundamental(session, target_codes: set[str] = None):
    today = date.today().isoformat()
    df = query_wencai(FUNDAMENTAL_QUERY)
    if df.empty:
        logger.warning("Fundamental query returned empty")
        return 0

    code_col = _find_col(df, ["股票代码", "代码"])
    if not code_col:
        logger.error(f"No code column. Available: {df.columns.tolist()}")
        return 0

    count = 0
    for _, row in df.iterrows():
        code = normalize_code(row[code_col])
        if target_codes and code not in target_codes:
            continue
        record = {"code": code, "date": today}
        for field, candidates in FIELD_MAP.items():
            col = _find_col(df, candidates)
            try:
                record[field] = float(row[col]) if col and row.get(col) is not None else None
            except (TypeError, ValueError):
                record[field] = None
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"Fundamental upsert failed for {code}: {e}")

    session.commit()
    logger.info(f"Fundamental data collected: {count} stocks")
    return count
