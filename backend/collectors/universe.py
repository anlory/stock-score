import json
import logging
from datetime import date
from backend.collectors.tushare_client import get_pro, to_ts_date, ts_call
from backend.collectors import tushare_client
from backend.collectors.base import query_wencai, normalize_code
from backend.collectors.hk_us.universe import sync_hk_us_universe
from backend.database import upsert
from backend.models import Stock

logger = logging.getLogger(__name__)

_INDICES = {
    "sz50":   {"name": "上证50",   "query": "上证50成分股"},
    "hs300":  {"name": "沪深300",  "query": "沪深300成分股"},
    "zz500":  {"name": "中证500",  "query": "中证500成分股"},
    "zz1000": {"name": "中证1000", "query": "中证1000成分股"},
    "cyb":    {"name": "创业板指", "query": "创业板指成分股"},
    "kcb50":  {"name": "科创50",   "query": "科创50成分股"},
}


def _get_market(code: str) -> str:
    if code.startswith(("6", "5", "9")):
        return "SH"
    if code.startswith(("4", "8")):
        return "BJ"
    return "SZ"


def _normalize(ts_code: str) -> str:
    return ts_code.split(".")[0]


def _fetch_index_constituents() -> dict[str, dict]:
    """Fetch all index constituents via pywencai. Returns {code: {name, tags}}."""
    all_stocks: dict[str, dict] = {}

    for tag, info in _INDICES.items():
        logger.info(f"Fetching {info['name']}...")
        try:
            df = query_wencai(info["query"], loop=True)
        except Exception as e:
            logger.warning(f"wencai fetch failed for {info['name']}: {e}")
            continue
        if df is None or df.empty:
            logger.warning(f"No data for {info['name']}")
            continue

        code_col = next((c for c in df.columns if "代码" in c or c == "code"), None)
        name_col = next((c for c in df.columns if "简称" in c), None)
        if not code_col:
            continue

        count = 0
        for _, row in df.iterrows():
            code = normalize_code(row[code_col])
            if not code:
                continue
            if code not in all_stocks:
                all_stocks[code] = {
                    "name": str(row.get(name_col) or code) if name_col else code,
                    "tags": [tag],
                }
            else:
                if tag not in all_stocks[code]["tags"]:
                    all_stocks[code]["tags"].append(tag)
            count += 1
        logger.info(f"{info['name']}: {count} stocks")

    return all_stocks


def _load_constituents_from_db(session) -> dict[str, dict]:
    """Load index constituents already stored in DB."""
    conditions = [Stock.index_tags.contains(tag) for tag in _INDICES]
    from sqlalchemy import or_
    stocks = session.query(Stock).filter(or_(*conditions)).all()
    if not stocks:
        return {}

    # Collect all tags present in DB
    db_tags: set[str] = set()
    result = {}
    for s in stocks:
        if not s.code:
            continue
        try:
            tags = json.loads(s.index_tags) if s.index_tags else []
        except (json.JSONDecodeError, TypeError):
            tags = []
        db_tags.update(tags)
        result[s.code] = {"name": s.name, "industry": s.industry, "tags": tags}

    # Cache is valid only if ALL configured indices are present
    missing = set(_INDICES.keys()) - db_tags
    if missing:
        logger.info(f"Cache missing indices: {missing}, will re-fetch")
        return {}

    return result


def sync_universe(session, watchlist_codes: list[str] = None, today: str = None) -> int:
    pro = get_pro()

    # 1. THS industry index list → fill INDUSTRY_TS_CODE_MAP
    ths_df = ts_call(pro.ths_index, exchange="A", type="N")
    if ths_df is not None and not ths_df.empty:
        for _, row in ths_df.iterrows():
            name = str(row.get("name") or "")
            ts_code = str(row.get("ts_code") or "")
            if name and ts_code:
                tushare_client.INDUSTRY_TS_CODE_MAP[name] = ts_code

    # 2. Index constituents: use DB cache if exists, otherwise fetch via wencai
    index_stocks = _load_constituents_from_db(session)
    if not index_stocks:
        logger.info("No cached constituents, fetching via wencai...")
        index_stocks = _fetch_index_constituents()
        if not index_stocks:
            logger.warning("Failed to fetch index constituents")
            return session.query(Stock).count()

        # Enrich with industry from stock_basic
        basic_df = ts_call(pro.stock_basic,
            exchange="", list_status="L",
            fields="ts_code,name,industry"
        )
        basic_info: dict[str, str] = {}
        if basic_df is not None and not basic_df.empty:
            for _, row in basic_df.iterrows():
                basic_info[_normalize(row["ts_code"])] = str(row.get("industry") or "")

        for code, info in index_stocks.items():
            upsert(session, Stock, {
                "code": code, "name": info["name"], "market": _get_market(code),
                "industry": basic_info.get(code, ""),
                "is_watchlist": False, "index_tags": json.dumps(info.get("tags", [])),
            }, ["code"])
        session.commit()
        logger.info(f"Index constituents cached: {len(index_stocks)} stocks")
    else:
        logger.info(f"Using cached constituents: {len(index_stocks)} stocks")

    # 3. Watchlist
    if watchlist_codes:
        for raw_code in watchlist_codes:
            code = raw_code.zfill(6)
            existing = session.get(Stock, code)
            if existing:
                existing.is_watchlist = True
            else:
                upsert(session, Stock, {
                    "code": code,
                    "name": code,
                    "market": _get_market(code),
                    "industry": "",
                    "is_watchlist": True,
                    "index_tags": "[]",
                }, ["code"])

    session.commit()

    # 3.5 HK/US index sync
    try:
        hk_us_count = sync_hk_us_universe(session)
        logger.info(f"HK/US sync: {hk_us_count} stocks")
    except Exception as e:
        logger.error(f"HK/US universe sync failed: {e}")

    # 4. Remove stale stocks not in index and not watchlisted
    valid_codes = set(index_stocks.keys())
    hk_us_stocks = session.query(Stock).filter(
        ~Stock.market.in_(["SH", "SZ", "BJ"])
    ).all()
    valid_codes.update(s.code for s in hk_us_stocks)
    for wl in (watchlist_codes or []):
        valid_codes.add(wl.zfill(6))
    stale = session.query(Stock).filter(
        ~Stock.code.in_(valid_codes),
        Stock.is_watchlist == False,
    ).all()
    for s in stale:
        session.delete(s)
    if stale:
        session.commit()
        logger.info(f"Removed {len(stale)} stale stocks")

    total = session.query(Stock).count()
    logger.info(f"Universe synced: {total} stocks")
    return total
