import logging
from datetime import date
from backend.collectors.base import query_wencai, normalize_code
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)

CAPITAL_QUERY = (
    "股票代码,"
    "今日主力净流入,5日主力净流入,"
    "今日超大单净流入,"
    "北向资金净买入额,融资净买入额"
)

FIELD_MAP = {
    "main_inflow_today":  ["今日主力净流入", "主力净流入"],
    "main_inflow_5d":     ["5日主力净流入"],
    "super_large_inflow": ["今日超大单净流入", "超大单净流入"],
    "north_inflow":       ["北向资金净买入额", "北向净买入"],
    "margin_net_buy":     ["融资净买入额", "融资净买入"],
}

def _find_col(df, candidates):
    return next((c for c in candidates if c in df.columns), None)

def collect_capital(session, target_codes: set[str] = None):
    today = date.today().isoformat()
    df = query_wencai(CAPITAL_QUERY)
    if df.empty:
        logger.warning("Capital query returned empty")
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
            logger.error(f"Capital upsert failed for {code}: {e}")

    session.commit()
    logger.info(f"Capital data collected: {count} stocks")
    return count
