import logging
from datetime import date
from backend.collectors.base import query_wencai, normalize_code
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)

NEWS_QUERY = (
    "股票代码,"
    "近30日研报数量,最新研报评级,"
    "最新公告类型,舆情情感分"
)

FIELD_MAP = {
    "report_count":      ["近30日研报数量", "研报数量"],
    "report_rating":     ["最新研报评级", "研报评级"],
    "announcement_type": ["最新公告类型", "公告类型"],
    "news_sentiment":    ["舆情情感分", "情感分"],
}

def _find_col(df, candidates):
    return next((c for c in candidates if c in df.columns), None)

def collect_news(session, target_codes: set[str] = None):
    today = date.today().isoformat()
    df = query_wencai(NEWS_QUERY)
    if df.empty:
        logger.warning("News query returned empty")
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
            if field == "report_count":
                try:
                    record[field] = int(val) if val is not None else None
                except (TypeError, ValueError):
                    record[field] = None
            elif field == "news_sentiment":
                try:
                    record[field] = float(val) if val is not None else None
                except (TypeError, ValueError):
                    record[field] = None
            else:
                record[field] = str(val) if val is not None else None
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"News upsert failed for {code}: {e}")

    session.commit()
    logger.info(f"News data collected: {count} stocks")
    return count
