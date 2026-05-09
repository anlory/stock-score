# backend/collectors/hk_us/news.py
"""News collector for HK/US stocks using yfinance (sequential, rate-limited)."""

import logging
import time

import yfinance as yf

from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)
_DELAY = 0.5


def _to_yf_symbol(code: str, market: str) -> str:
    if market == "HK":
        return f"{int(code):04d}.HK"
    return code


def collect_hk_us_news(session, target_codes: dict[str, str], today: str) -> int:
    """Collect news count for HK/US stocks (sequential, rate-limited)."""
    if not target_codes:
        return 0

    count = 0
    total = len(target_codes)

    for i, (code, market) in enumerate(target_codes.items(), 1):
        try:
            symbol = _to_yf_symbol(code, market)
            news = yf.Ticker(symbol).news
            report_count = len(news) if news else 0

            upsert(session, DailyData, {
                "code": code, "date": today,
                "report_count": report_count,
            }, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"HK/US news failed for {code}: {e}")

        if i % 20 == 0 or i == total:
            logger.info(f"HK/US News: {i}/{total}")
        time.sleep(_DELAY)

    session.commit()
    logger.info(f"HK/US news data collected: {count} stocks")
    return count
