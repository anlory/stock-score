import logging
import re
from datetime import date
from backend.collectors.base import query_wencai, normalize_code
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)

QUERY = "市盈率 市净率 ROE 净利润同比增长率 总市值"

COL_PATTERNS = {
    "pe":                [r"市盈率"],
    "pb":                [r"市净率"],
    "roe":               [r"roe"],
    "profit_growth_yoy": [r"净利润同比"],
    "market_cap":        [r"总市值"],
}


def _build_col_map(columns):
    mapping = {}
    for field, patterns in COL_PATTERNS.items():
        for col in columns:
            if any(re.search(p, col.lower()) for p in patterns):
                mapping[field] = col
                break
    return mapping


def collect_fundamental(session, target_codes: set[str] = None):
    today = date.today().isoformat()
    codes = sorted(target_codes) if target_codes else []
    if not codes:
        return 0

    count = 0
    # 分批查询，每批50个股票
    for i in range(0, len(codes), 50):
        batch = codes[i:i+50]
        codes_str = " ".join(batch)
        df = query_wencai(f"{codes_str} 市盈率 市净率 ROE 净利润同比增长率 总市值")
        if df.empty:
            continue

        code_col = next((c for c in df.columns if "代码" in c or c == "code"), None)
        if not code_col:
            continue

        col_map = _build_col_map(df.columns.tolist())
        seen = set()
        for _, row in df.iterrows():
            code = normalize_code(row[code_col])
            if code in seen or code not in target_codes:
                continue
            seen.add(code)
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
                logger.error(f"Fundamental upsert failed for {code}: {e}")

    session.commit()
    logger.info(f"Fundamental data collected: {count} stocks")
    return count
