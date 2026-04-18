import logging
import re
from datetime import date
from backend.collectors.base import query_wencai, normalize_code
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)

QUERY = "涨跌幅 换手率 量比 连续涨停天数 所属行业板块涨幅排名"

COL_PATTERNS = {
    "change_pct":           [r"涨跌幅"],
    "turnover_rate":        [r"换手率"],
    "volume_ratio":         [r"量比"],
    "consecutive_limit_up": [r"连续涨停", r"连板"],
    "sector_heat_rank":     [r"板块.*涨幅排名", r"板块排名"],
}


def _build_col_map(columns):
    mapping = {}
    for field, patterns in COL_PATTERNS.items():
        for col in columns:
            if any(re.search(p, col) for p in patterns):
                mapping[field] = col
                break
    return mapping


def collect_market_heat(session, target_codes: set[str] = None):
    today = date.today().isoformat()
    df = query_wencai(QUERY)
    if df.empty:
        logger.warning("Market heat query returned empty")
        return 0

    code_col = next((c for c in df.columns if "代码" in c or c == "code"), None)
    if not code_col:
        return 0

    col_map = _build_col_map(df.columns.tolist())
    logger.info(f"Heat col map: {col_map}")

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
            val = row.get(col)
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
