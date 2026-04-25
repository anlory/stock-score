import json
import logging
import threading
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.collectors.tushare_client import get_pro, to_ts_code
from backend.models import Stock

logger = logging.getLogger(__name__)
CACHE_TTL_DAYS = 30

_concept_map: dict[str, list[str]] = {}
_concept_map_lock = threading.Lock()
_concept_map_built = False


def _build_concept_map():
    global _concept_map_built
    pro = get_pro()
    try:
        concepts_df = pro.concept()
        if concepts_df is None or concepts_df.empty:
            return
        result: dict[str, list[str]] = {}
        for _, row in concepts_df.iterrows():
            cid = str(row.get("code") or "")
            cname = str(row.get("name") or "")
            if not cid:
                continue
            try:
                detail = pro.concept_detail(id=cid, fields="ts_code,name")
                if detail is None or detail.empty:
                    continue
                for _, drow in detail.iterrows():
                    ts = str(drow.get("ts_code") or "")
                    if ts:
                        result.setdefault(ts, []).append(cname)
            except Exception:
                pass
        with _concept_map_lock:
            _concept_map.update(result)
            _concept_map_built = True
    except Exception as e:
        logger.warning(f"concept map build failed: {e}")


def _ensure_concept_map():
    global _concept_map_built
    if not _concept_map_built:
        t = threading.Thread(target=_build_concept_map, daemon=True)
        t.start()


def _fetch_individual_info(code: str) -> dict | None:
    pro = get_pro()
    ts_code = to_ts_code(code)
    try:
        df = pro.stock_basic(
            ts_code=ts_code, list_status="L",
            fields="ts_code,name,industry,list_date,total_share,float_share"
        )
        if df is None or df.empty:
            return None
        row = df.iloc[0]
        total_share = _sf(row.get("total_share"))
        float_share = _sf(row.get("float_share"))
        list_date_raw = str(row.get("list_date") or "")
        list_date = f"{list_date_raw[:4]}-{list_date_raw[4:6]}-{list_date_raw[6:]}" if len(list_date_raw) == 8 else None
        return {
            "industry": str(row.get("industry") or ""),
            "total_share": round(total_share / 10000, 4) if total_share else None,
            "float_share": round(float_share / 10000, 4) if float_share else None,
            "list_date": list_date,
        }
    except Exception as e:
        logger.warning(f"stock_basic failed for {code}: {e}")
        return None


def _fetch_business(session: Session, code: str) -> str | None:
    pro = get_pro()
    ts_code = to_ts_code(code)
    try:
        df = pro.stock_company(ts_code=ts_code, fields="ts_code,business_scope")
        if df is None or df.empty:
            return None
        return str(df.iloc[0].get("business_scope") or "")[:200] or None
    except Exception as e:
        logger.warning(f"stock_company failed for {code}: {e}")
        return None


def _fetch_concepts(code: str) -> list[str]:
    _ensure_concept_map()
    ts_code = to_ts_code(code)
    with _concept_map_lock:
        return _concept_map.get(ts_code, [])[:10]


def _cache_valid(stock: Stock) -> bool:
    if not stock.profile_updated_at:
        return False
    return stock.profile_updated_at > datetime.now() - timedelta(days=CACHE_TTL_DAYS)


def fetch_profile(session: Session, code: str) -> Stock | None:
    code = code.zfill(6)
    stock = session.get(Stock, code)
    if not stock:
        return None
    if _cache_valid(stock):
        return stock

    try:
        info = _fetch_individual_info(code)
    except Exception as e:
        logger.warning(f"profile fetch failed for {code}: {e}")
        return stock

    concepts = _fetch_concepts(code)
    business = _fetch_business(session, code)

    if info:
        if info.get("total_share") is not None:
            stock.total_share = info["total_share"]
        if info.get("float_share") is not None:
            stock.float_share = info["float_share"]
        if info.get("industry"):
            stock.industry = info["industry"]
        if info.get("list_date"):
            stock.list_date = info["list_date"]
    if concepts:
        stock.concepts = json.dumps(concepts, ensure_ascii=False)
    if business:
        stock.business = business

    stock.profile_updated_at = datetime.now()
    session.commit()
    return stock


def _sf(val):
    try:
        import math
        v = float(val)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None
