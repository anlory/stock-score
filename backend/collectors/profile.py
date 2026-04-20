import json
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.models import Stock

logger = logging.getLogger(__name__)

CACHE_TTL_DAYS = 30


def _fetch_individual_info(code: str) -> dict:
    """Return {industry, total_share, float_share, list_date} from akshare."""
    import akshare as ak
    df = ak.stock_individual_info_em(symbol=code)
    kv = dict(zip(df["item"], df["value"]))
    def _to_float(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    list_date = kv.get("上市时间")
    if list_date and len(str(list_date)) == 8:
        s = str(list_date)
        list_date = f"{s[0:4]}-{s[4:6]}-{s[6:8]}"

    total = _to_float(kv.get("总股本"))
    floatv = _to_float(kv.get("流通股"))
    return {
        "industry": kv.get("行业"),
        "total_share": round(total / 1e8, 4) if total else None,
        "float_share": round(floatv / 1e8, 4) if floatv else None,
        "list_date": list_date,
    }


def _fetch_business(code: str) -> str | None:
    """Return a short business description (<=200 chars) via akshare."""
    import akshare as ak
    try:
        df = ak.stock_zyjs_ths(symbol=code)
        if df is None or df.empty:
            return None
        for col in ("主营业务", "产品名称", "经营范围"):
            if col in df.columns:
                val = df[col].iloc[0]
                if val:
                    s = str(val).strip()
                    return s[:200]
        return None
    except Exception as e:
        logger.warning(f"business fetch failed for {code}: {e}")
        return None


def _fetch_concepts(code: str) -> list[str]:
    """Return list of concept board names via pywencai; empty on failure."""
    try:
        from backend.collectors.base import query_wencai
        df = query_wencai(f"{code} 所属概念板块")
        if df is None or df.empty:
            return []
        for col in df.columns:
            if "概念" in col or "板块" in col:
                raw = df[col].iloc[0]
                if isinstance(raw, str):
                    parts = [p.strip() for p in raw.replace("，", ",").split(",") if p.strip()]
                    return parts[:10]
                if isinstance(raw, list):
                    return [str(x) for x in raw[:10]]
        return []
    except Exception as e:
        logger.warning(f"concepts fetch failed for {code}: {e}")
        return []


def _cache_valid(stock: Stock) -> bool:
    if not stock.profile_updated_at:
        return False
    return stock.profile_updated_at > datetime.now() - timedelta(days=CACHE_TTL_DAYS)


def fetch_profile(session: Session, code: str) -> Stock | None:
    """Return Stock with profile fields populated. Uses 30-day cache."""
    code = code.zfill(6)
    stock = session.get(Stock, code)
    if not stock:
        return None
    if _cache_valid(stock):
        return stock

    try:
        info = _fetch_individual_info(code)
        business = _fetch_business(code)
        concepts = _fetch_concepts(code)
    except Exception as e:
        logger.error(f"profile fetch failed for {code}: {e}")
        return stock

    if info.get("industry") is not None:
        stock.industry = info["industry"]
    if info.get("total_share") is not None:
        stock.total_share = info["total_share"]
    if info.get("float_share") is not None:
        stock.float_share = info["float_share"]
    if info.get("list_date") is not None:
        stock.list_date = info["list_date"]
    if business:
        stock.business = business
    if concepts:
        stock.concepts = json.dumps(concepts, ensure_ascii=False)
    stock.profile_updated_at = datetime.now()
    session.commit()
    return stock
