import logging
import re
from datetime import date
from backend.collectors.base import query_wencai, normalize_code
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)

QUERY = "主力资金流向 特大单净额 陆股通净买入额 融资净买入额"

COL_PATTERNS = {
    "main_inflow_today":  [r"主力资金流向", r"主力净流入"],
    "super_large_inflow": [r"特大单净"],
    "north_inflow":       [r"陆股通净买入", r"北向.*净"],
    "margin_net_buy":     [r"融资净买入"],
}


def _build_col_map(columns):
    mapping = {}
    for field, patterns in COL_PATTERNS.items():
        for col in columns:
            if any(re.search(p, col) for p in patterns):
                mapping[field] = col
                break
    return mapping


def collect_capital(session, target_codes: set[str] = None):
    today = date.today().isoformat()
    df = query_wencai(QUERY)
    if df.empty:
        logger.warning("Capital query returned empty")
        return 0

    code_col = next((c for c in df.columns if "代码" in c or c == "code"), None)
    if not code_col:
        logger.error(f"No code column. Columns: {df.columns.tolist()}")
        return 0

    col_map = _build_col_map(df.columns.tolist())
    logger.info(f"Capital col map: {col_map}")

    count = 0
    seen = set()
    for _, row in df.iterrows():
        code = normalize_code(row[code_col])
        if code in seen:
            continue
        seen.add(code)
        if target_codes and code not in target_codes:
            continue
        record = {"code": code, "date": today}
        for field, col in col_map.items():
            try:
                record[field] = float(row[col]) if row.get(col) is not None else None
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
