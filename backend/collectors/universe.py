import json
import logging
from backend.collectors.base import query_wencai, normalize_code
from backend.database import upsert
from backend.models import Stock

logger = logging.getLogger(__name__)

def get_hot_sector_stocks() -> list[str]:
    """Get stocks from top 10 hot sectors today via pywencai."""
    df = query_wencai("涨幅最大的10个行业板块", query_type="plate")
    if df.empty:
        logger.warning("Hot sector query returned empty")
        return []

    sector_col = next((c for c in df.columns if "板块" in c or "行业" in c or "名称" in c), None)
    if not sector_col:
        logger.warning(f"Cannot find sector column in: {df.columns.tolist()}")
        return []

    sectors = df[sector_col].dropna().tolist()[:10]
    codes = []
    for sector in sectors:
        sector_df = query_wencai(f"{sector} 涨幅最大的5只股票 股票代码")
        if sector_df.empty:
            continue
        code_col = next((c for c in sector_df.columns if "代码" in c), None)
        if code_col:
            top5 = sector_df[code_col].dropna().tolist()[:5]
            codes.extend([normalize_code(c) for c in top5])

    return list(set(codes))

def sync_universe(session, watchlist_codes: list[str] = None):
    """Sync full stock universe (index + hot sectors + watchlist) to DB."""
    # 1. 指数成分股
    index_map = {
        "沪深300成分股 股票代码 股票名称": "hs300",
        "中证500成分股 股票代码 股票名称": "zz500",
        "创业板指成分股 股票代码 股票名称": "cyb",
    }
    index_stocks: dict[str, dict] = {}
    for query, tag in index_map.items():
        df = query_wencai(query)
        if df.empty:
            continue
        code_col = next((c for c in df.columns if "代码" in c), None)
        name_col = next((c for c in df.columns if "名称" in c), None)
        if not code_col:
            continue
        for _, row in df.iterrows():
            code = normalize_code(row[code_col])
            name = str(row[name_col]) if name_col else code
            if code not in index_stocks:
                index_stocks[code] = {"name": name, "tags": []}
            index_stocks[code]["tags"].append(tag)

    for code, info in index_stocks.items():
        market = "SH" if code.startswith("6") else "SZ"
        upsert(session, Stock, {
            "code": code, "name": info["name"], "market": market,
            "is_watchlist": False, "index_tags": json.dumps(info["tags"]),
        }, ["code"])

    # 2. 热门板块
    hot_codes = get_hot_sector_stocks()
    for code in hot_codes:
        existing = session.get(Stock, code)
        if not existing:
            market = "SH" if code.startswith("6") else "SZ"
            upsert(session, Stock, {
                "code": code, "name": code, "market": market,
                "is_watchlist": False, "index_tags": "[]",
            }, ["code"])

    # 3. 自选股
    if watchlist_codes:
        for raw_code in watchlist_codes:
            code = normalize_code(raw_code)
            market = "SH" if code.startswith("6") else "SZ"
            existing = session.get(Stock, code)
            if existing:
                existing.is_watchlist = True
            else:
                upsert(session, Stock, {
                    "code": code, "name": code, "market": market,
                    "is_watchlist": True, "index_tags": "[]",
                }, ["code"])

    session.commit()
    total = session.query(Stock).count()
    logger.info(f"Universe synced: {total} stocks")
    return total
