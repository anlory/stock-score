# backend/collectors/hk_us/profile.py
"""Profile collector for HK/US stocks using yfinance .info with 30-day cache."""

import logging
import math
from datetime import datetime, timedelta

import yfinance as yf
from sqlalchemy.orm import Session

from backend.models import Stock

logger = logging.getLogger(__name__)
_CACHE_TTL_DAYS = 30


def _to_yf_symbol(code: str, market: str) -> str:
    """Convert internal code to yfinance symbol."""
    if market == "HK":
        return f"{int(code):04d}.HK"
    return code


def _sf(val, default=None):
    """Safely convert to float."""
    try:
        v = float(val)
        return None if math.isnan(v) else round(v, 4)
    except (TypeError, ValueError):
        return default


def _cache_valid(stock: Stock) -> bool:
    """Check if the profile cache is still valid."""
    if not stock.profile_updated_at:
        return False
    return stock.profile_updated_at > datetime.now() - timedelta(days=_CACHE_TTL_DAYS)


def fetch_hk_us_profile(session: Session, code: str) -> Stock | None:
    """Fetch and update profile for a single HK/US stock.

    Uses a 30-day cache to avoid repeated API calls.

    Args:
        session: SQLAlchemy session.
        code: Internal stock code (e.g. "00700" or "AAPL").

    Returns:
        Updated Stock object, or None if stock not found in DB.
    """
    stock = session.get(Stock, code)
    if not stock:
        return None
    if _cache_valid(stock):
        return stock

    try:
        symbol = _to_yf_symbol(code, stock.market or "US")
        info = yf.Ticker(symbol).info
        if not info:
            return stock

        # Name
        if info.get("shortName") or info.get("longName"):
            stock.name = info.get("shortName") or info.get("longName")

        # Industry / sector
        if info.get("sector"):
            stock.industry = str(info["sector"])

        # Introduction
        if info.get("longBusinessSummary"):
            stock.introduction = str(info["longBusinessSummary"])[:500]

        # Market cap (convert to 亿元)
        market_cap_raw = _sf(info.get("marketCap"))
        if market_cap_raw:
            stock.total_mv = round(market_cap_raw / 1e8, 4)

        # Total shares (convert to 亿股)
        shares_raw = _sf(info.get("sharesOutstanding"))
        if shares_raw:
            stock.total_share = round(shares_raw / 1e8, 4)

        # PE / PB
        pe = _sf(info.get("trailingPE"))
        if pe is not None:
            stock.pe = pe
        pb = _sf(info.get("priceToBook"))
        if pb is not None:
            stock.pb = pb

        # Website
        if info.get("website"):
            stock.website = str(info["website"])

        # City
        if info.get("city"):
            stock.city = str(info["city"])

        # Province (use country for HK/US stocks)
        if info.get("country"):
            stock.province = str(info["country"])

        stock.profile_updated_at = datetime.now()
        session.commit()
        return stock

    except Exception as e:
        logger.error(f"HK/US profile fetch failed for {code}: {e}")
        return stock
