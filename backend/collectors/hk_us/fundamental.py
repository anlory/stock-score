# backend/collectors/hk_us/fundamental.py
"""Fundamental data collector for HK/US stocks using yfinance .info."""

import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf

from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)
_MAX_WORKERS = 5


def _to_yf_symbol(code: str, market: str) -> str:
    """Convert internal code to yfinance symbol."""
    if market == "HK":
        return f"{int(code):04d}.HK"
    return code


def _sf(val, default=None):
    """Safely convert to float, returning default on failure."""
    try:
        v = float(val)
        return None if math.isnan(v) else round(v, 4)
    except (TypeError, ValueError):
        return default


def _process_one(code: str, market: str, today: str) -> dict | None:
    """Fetch fundamental data for a single HK/US stock."""
    try:
        symbol = _to_yf_symbol(code, market)
        info = yf.Ticker(symbol).info
        if not info:
            return None

        market_cap_raw = _sf(info.get("marketCap"))
        # Convert to 亿元 (1 billion yuan = 1e8; USD 1e9 -> 1e8 requires conversion,
        # but we store raw marketCap/1e8 as per spec)
        market_cap = round(market_cap_raw / 1e8, 4) if market_cap_raw else None

        roe_raw = _sf(info.get("returnOnEquity"))
        # returnOnEquity from yfinance is already a ratio (e.g. 0.25 = 25%), convert to %
        roe = round(roe_raw * 100, 4) if roe_raw is not None else None

        profit_raw = _sf(info.get("earningsGrowth"))
        # earningsGrowth is also a ratio, convert to %
        profit_growth_yoy = round(profit_raw * 100, 4) if profit_raw is not None else None

        record = {
            "code": code,
            "date": today,
            "pe": _sf(info.get("trailingPE")),
            "pb": _sf(info.get("priceToBook")),
            "market_cap": market_cap,
            "roe": roe,
            "profit_growth_yoy": profit_growth_yoy,
        }
        return record
    except Exception as e:
        logger.error(f"HK/US fundamental failed for {code}: {e}")
        return None


def collect_hk_us_fundamental(session, target_codes: dict[str, str], today: str) -> int:
    """Collect fundamental data for HK/US stocks.

    Args:
        session: SQLAlchemy session.
        target_codes: dict mapping code -> market ("US" or "HK").
        today: ISO date string (YYYY-MM-DD).

    Returns:
        Number of stocks successfully collected.
    """
    if not target_codes:
        logger.warning("No target codes for HK/US fundamental collection")
        return 0

    results = []
    done = 0
    total = len(target_codes)

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {
            pool.submit(_process_one, code, market, today): code
            for code, market in target_codes.items()
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
            done += 1
            if done % 20 == 0 or done == total:
                logger.info(f"HK/US Fundamental: {done}/{total}")

    count = 0
    for record in results:
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"HK/US Fundamental upsert failed for {record.get('code')}: {e}")

    session.commit()
    logger.info(f"HK/US fundamental data collected: {count} stocks")
    return count
