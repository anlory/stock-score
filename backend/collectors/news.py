import logging
from datetime import date
from backend.collectors.base import query_wencai, build_col_map, normalize_code
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)

COL_PATTERNS = {
    "report_count":  ["研报数量", "区间研究报告数量"],
    "report_rating": ["研报评级", "同花顺评级"],
}


def collect_news(session, target_codes: set[str] = None):
    today = date.today().isoformat()
    codes = sorted(target_codes) if target_codes else []
    if not codes:
        return 0

    count = 0
    for code in codes:
        try:
            df = query_wencai(f"{code} 近30日研报数量 研报评级")
            if df.empty:
                continue

            code_col = next((c for c in df.columns if "代码" in c or c == "code"), None)
            if not code_col:
                continue

            col_map = build_col_map(df.columns.tolist(), COL_PATTERNS)
            record = {"code": code, "date": today}
            for field, col in col_map.items():
                # Take the first non-null value across all rows
                for _, row in df.iterrows():
                    row_code = normalize_code(row[code_col])
                    if row_code != code:
                        continue
                    val = row.get(col)
                    if val is not None and str(val) != "nan":
                        if field == "report_count":
                            try:
                                record[field] = int(val)
                            except (TypeError, ValueError):
                                pass
                        else:
                            record[field] = str(val)
                        break

            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"News upsert failed for {code}: {e}")

    session.commit()
    logger.info(f"News data collected: {count} stocks")
    return count
