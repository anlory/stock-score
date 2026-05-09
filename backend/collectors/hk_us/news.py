# backend/collectors/hk_us/news.py
"""News collector for HK/US stocks using yfinance."""

import logging
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


def _process_one(code: str, market: str, today: str) -> dict | None:
    """Fetch news count for a single HK/US stock."""
    try:
        symbol = _to_yf_symbol(code, market)
        news = yf.Ticker(symbol).news
        report_count = len(news) if news else 0

        return {
            "code": code,
            "date": today,
            "report_count": report_count,
        }
    except Exception as e:
        logger.error(f"HK/US news failed for {code}: {e}")
        return None


def collect_hk_us_news(session, target_codes: dict[str, str], today: str) -> int:
    """Collect news data for HK/US stocks.

    Args:
        session: SQLAlchemy session.
        target_codes: dict mapping code -> market ("US" or "HK").
        today: ISO date string (YYYY-MM-DD).

    Returns:
        Number of stocks successfully collected.
    """
    if not target_codes:
        logger.warning("No target codes for HK/US news collection")
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
                logger.info(f"HK/US News: {done}/{total}")

    count = 0
    for record in results:
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"HK/US News upsert failed for {record.get('code')}: {e}")

    session.commit()
    logger.info(f"HK/US news data collected: {count} stocks")
    return count
