import logging
from datetime import date
from backend.collectors.base import query_wencai, normalize_code
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)

TECHNICAL_QUERY = (
    "股票代码,最新价,"
    "5日均线,13日均线,30日均线,"
    "MACD的DIF值,MACD的DEA值,MACD,"
    "RSI,"
    "KDJ的K值,KDJ的D值,KDJ的J值,"
    "布林线上轨,布林线中轨,布林线下轨,"
    "量比"
)

FIELD_MAP = {
    "close":      ["最新价", "收盘价"],
    "ma5":        ["5日均线", "MA5"],
    "ma13":       ["13日均线", "MA13"],
    "ma30":       ["30日均线", "MA30"],
    "macd_dif":   ["MACD的DIF值", "DIF"],
    "macd_dea":   ["MACD的DEA值", "DEA"],
    "macd_bar":   ["MACD", "MACD柱"],
    "rsi14":      ["RSI", "RSI(14)"],
    "kdj_k":      ["KDJ的K值", "K"],
    "kdj_d":      ["KDJ的D值", "D"],
    "kdj_j":      ["KDJ的J值", "J"],
    "boll_upper": ["布林线上轨", "BOLL_UPPER"],
    "boll_mid":   ["布林线中轨", "BOLL_MID"],
    "boll_lower": ["布林线下轨", "BOLL_LOWER"],
    "volume_ratio": ["量比"],
}

def _find_col(df, candidates: list[str]):
    for c in candidates:
        if c in df.columns:
            return c
    return None

def collect_technical(session, target_codes: set[str] = None):
    """Collect technical indicators for all stocks via pywencai."""
    today = date.today().isoformat()
    df = query_wencai(TECHNICAL_QUERY)
    if df.empty:
        logger.warning("Technical query returned empty DataFrame")
        return 0

    code_col = _find_col(df, ["股票代码", "代码", "code"])
    if not code_col:
        logger.error(f"Cannot find code column. Available: {df.columns.tolist()}")
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
            logger.error(f"Upsert failed for {code}: {e}")

    session.commit()
    logger.info(f"Technical data collected: {count} stocks")
    return count
