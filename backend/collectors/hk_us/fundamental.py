# backend/collectors/hk_us/fundamental.py
"""Fundamental data collector for HK/US stocks using yfinance .info (sequential with rate limiting)."""

import logging
import math
import time

import yfinance as yf

from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)
_DELAY = 0.5  # seconds between requests to avoid rate limiting


def _to_yf_symbol(code: str, market: str) -> str:
    if market == "HK":
        return f"{int(code):04d}.HK"
    return code


def _sf(val, default=None):
    try:
        v = float(val)
        return None if math.isnan(v) else round(v, 4)
    except (TypeError, ValueError):
        return default


def collect_hk_us_fundamental(session, target_codes: dict[str, str], today: str) -> int:
    """Collect fundamental data for HK/US stocks (sequential, rate-limited)."""
    if not target_codes:
        logger.warning("No target codes for HK/US fundamental collection")
        return 0

    results = []
    total = len(target_codes)

    for i, (code, market) in enumerate(target_codes.items(), 1):
        try:
            symbol = _to_yf_symbol(code, market)
            info = yf.Ticker(symbol).info
            if not info:
                continue

            market_cap_raw = _sf(info.get("marketCap"))
            market_cap = round(market_cap_raw / 1e8, 4) if market_cap_raw else None

            roe_raw = _sf(info.get("returnOnEquity"))
            roe = round(roe_raw * 100, 4) if roe_raw is not None else None

            profit_raw = _sf(info.get("earningsGrowth"))
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
            results.append(record)
        except Exception as e:
            logger.error(f"HK/US fundamental failed for {code}: {e}")

        if i % 20 == 0 or i == total:
            logger.info(f"HK/US Fundamental: {i}/{total}")
        time.sleep(_DELAY)

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
