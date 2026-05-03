import json
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.collectors.tushare_client import get_pro, to_ts_code, ts_call
from backend.models import Stock

logger = logging.getLogger(__name__)
CACHE_TTL_DAYS = 30

def _fetch_individual_info(code: str) -> dict | None:
    pro = get_pro()
    ts_code = to_ts_code(code)
    try:
        df = ts_call(pro.stock_basic,
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


def _fetch_company_info(code: str) -> dict | None:
    pro = get_pro()
    ts_code = to_ts_code(code)
    try:
        df = ts_call(pro.stock_company, ts_code=ts_code)
        if df is None or df.empty:
            return None
        row = df.iloc[0]
        setup_raw = str(row.get("setup_date") or "")
        return {
            "chairman": str(row.get("chairman") or ""),
            "manager": str(row.get("manager") or ""),
            "setup_date": f"{setup_raw[:4]}-{setup_raw[4:6]}-{setup_raw[6:]}" if len(setup_raw) == 8 else None,
            "province": str(row.get("province") or ""),
            "city": str(row.get("city") or ""),
            "introduction": str(row.get("introduction") or "")[:500] or None,
            "main_business": str(row.get("main_business") or "")[:300] or None,
            "business": str(row.get("business_scope") or "")[:300] or None,
            "website": str(row.get("website") or ""),
            "employees": _sf(row.get("employees")),
            "office": str(row.get("office") or ""),
        }
    except Exception as e:
        logger.warning(f"stock_company failed for {code}: {e}")
        return None


def _fetch_concepts(code: str) -> list[str]:
    pro = get_pro()
    ts_code = to_ts_code(code)
    try:
        df = ts_call(pro.concept_detail, ts_code=ts_code)
        if df is None or df.empty:
            return []
        skip = {"融资融券", "转融券标的", "融资标的股", "融券标的股", "标普道琼斯A股", "MSCI概念", "深股通", "沪股通", "优先股概念"}
        return [str(r) for r in df["concept_name"] if str(r) not in skip][:10]
    except Exception as e:
        logger.warning(f"concept fetch failed for {code}: {e}")
        return []


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
    company = _fetch_company_info(code)

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
    if company:
        for key in ("chairman", "manager", "setup_date", "province", "city",
                     "introduction", "main_business", "business", "website",
                     "office"):
            if company.get(key):
                setattr(stock, key, company[key])
        if company.get("employees") is not None:
            stock.employees = company["employees"]

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
