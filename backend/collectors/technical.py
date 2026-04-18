import logging
import re
from datetime import date
from backend.collectors.base import query_wencai, normalize_code
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)

QUERY = "收盘价 5日均线 13日均线 30日均线 macd的diff macd的dea macd的macd rsi的rsi1 kdj的k kdj的d kdj的j boll的upper boll的mid boll的lower 量比"

# Regex patterns for fuzzy column matching (问财返回的列名带日期后缀如 [20260417])
COL_PATTERNS = {
    "close":        [r"收盘价", r"最新价"],
    "ma5":          [r"5日均线"],
    "ma13":         [r"13日均线"],
    "ma30":         [r"30日均线"],
    "macd_dif":     [r"macd.*diff", r"dif值"],
    "macd_dea":     [r"macd.*dea", r"dea值"],
    "macd_bar":     [r"macd\(macd", r"macd值"],
    "rsi14":        [r"rsi.*rsi1", r"rsi\(14"],
    "kdj_k":        [r"kdj.*k[值(]", r"kdj\(k"],
    "kdj_d":        [r"kdj.*d[值(]", r"kdj\(d"],
    "kdj_j":        [r"kdj.*j[值(]", r"kdj\(j"],
    "boll_upper":   [r"boll.*upper"],
    "boll_mid":     [r"boll.*mid"],
    "boll_lower":   [r"boll.*lower"],
    "volume_ratio": [r"量比"],
}


def _match_col(columns: list[str], patterns: list[str]) -> str | None:
    for col in columns:
        col_lower = col.lower()
        for pat in patterns:
            if re.search(pat, col_lower):
                return col
    return None


def _build_col_map(columns: list[str]) -> dict[str, str]:
    mapping = {}
    for field, patterns in COL_PATTERNS.items():
        col = _match_col(columns, patterns)
        if col:
            mapping[field] = col
    return mapping


def collect_technical(session, target_codes: set[str] = None):
    today = date.today().isoformat()
    df = query_wencai(QUERY)
    if df.empty:
        logger.warning("Technical query returned empty")
        return 0

    code_col = next((c for c in df.columns if "代码" in c or c == "code"), None)
    if not code_col:
        logger.error(f"No code column. Columns: {df.columns.tolist()}")
        return 0

    col_map = _build_col_map(df.columns.tolist())
    logger.info(f"Technical col map: {col_map}")

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
                val = row.get(col)
                record[field] = float(val) if val is not None else None
            except (TypeError, ValueError):
                record[field] = None
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"Upsert failed for {code}: {e}")

    session.commit()
    logger.info(f"Technical data collected: {count} stocks")
    return count
