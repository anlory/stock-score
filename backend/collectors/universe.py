import json
import logging
from datetime import date
from backend.collectors.tushare_client import get_pro, to_ts_date
from backend.collectors import tushare_client
from backend.database import upsert
from backend.models import Stock

logger = logging.getLogger(__name__)


def _get_market(code: str) -> str:
    if code.startswith(("6", "5", "9")):
        return "SH"
    if code.startswith(("4", "8")):
        return "BJ"
    return "SZ"


def _normalize(ts_code: str) -> str:
    return ts_code.split(".")[0]


def sync_universe(session, watchlist_codes: list[str] = None) -> int:
    pro = get_pro()
    today_ts = to_ts_date(date.today().isoformat())

    # 1. Full stock basic info (name, industry)
    basic_df = pro.stock_basic(
        exchange="", list_status="L",
        fields="ts_code,name,industry,market"
    )
    basic_info: dict[str, dict] = {}
    if basic_df is not None and not basic_df.empty:
        for _, row in basic_df.iterrows():
            code = _normalize(row["ts_code"])
            basic_info[code] = {
                "name": str(row.get("name") or code),
                "industry": str(row.get("industry") or ""),
            }

    # 2. THS industry index list → fill INDUSTRY_TS_CODE_MAP
    ths_df = pro.ths_index(exchange="A", type="N")
    if ths_df is not None and not ths_df.empty:
        for _, row in ths_df.iterrows():
            name = str(row.get("name") or "")
            ts_code = str(row.get("ts_code") or "")
            if name and ts_code:
                tushare_client.INDUSTRY_TS_CODE_MAP[name] = ts_code

    # 3. Index components
    index_map = {
        "000300.SH": "hs300",
        "000905.SH": "zz500",
        "399006.SZ": "cyb",
    }
    index_stocks: dict[str, dict] = {}
    for idx_code, tag in index_map.items():
        try:
            df = pro.index_member(index_code=idx_code, fields="con_code,con_name")
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                code = _normalize(str(row.get("con_code") or ""))
                if not code:
                    continue
                if code not in index_stocks:
                    info = basic_info.get(code, {})
                    index_stocks[code] = {
                        "name": str(row.get("con_name") or info.get("name") or code),
                        "industry": info.get("industry", ""),
                        "tags": [],
                    }
                index_stocks[code]["tags"].append(tag)
        except Exception as e:
            logger.error(f"index_member failed for {idx_code}: {e}")

    for code, info in index_stocks.items():
        upsert(session, Stock, {
            "code": code, "name": info["name"], "market": _get_market(code),
            "industry": info["industry"],
            "is_watchlist": False, "index_tags": json.dumps(info["tags"]),
        }, ["code"])

    # 4. Hot sector stocks
    try:
        heat_df = pro.ths_daily(trade_date=today_ts)
        if heat_df is not None and not heat_df.empty and "pct_change" in heat_df.columns:
            top10 = heat_df.nlargest(10, "pct_change")["ts_code"].tolist()
            for ths_ts_code in top10:
                try:
                    member_df = pro.ths_member(ts_code=ths_ts_code)
                    if member_df is None or member_df.empty:
                        continue
                    for _, row in member_df.head(5).iterrows():
                        code = str(row.get("code") or "").zfill(6)
                        if not code or code == "000000":
                            continue
                        if not session.get(Stock, code):
                            info = basic_info.get(code, {})
                            upsert(session, Stock, {
                                "code": code,
                                "name": info.get("name", code),
                                "market": _get_market(code),
                                "industry": info.get("industry", ""),
                                "is_watchlist": False,
                                "index_tags": "[]",
                            }, ["code"])
                except Exception as e:
                    logger.warning(f"ths_member failed for {ths_ts_code}: {e}")
    except Exception as e:
        logger.warning(f"ths_daily failed: {e}")

    # 5. Watchlist
    if watchlist_codes:
        for raw_code in watchlist_codes:
            code = raw_code.zfill(6)
            existing = session.get(Stock, code)
            if existing:
                existing.is_watchlist = True
            else:
                info = basic_info.get(code, {})
                upsert(session, Stock, {
                    "code": code,
                    "name": info.get("name", code),
                    "market": _get_market(code),
                    "industry": info.get("industry", ""),
                    "is_watchlist": True,
                    "index_tags": "[]",
                }, ["code"])

    session.commit()
    total = session.query(Stock).count()
    logger.info(f"Universe synced: {total} stocks")
    return total
