# backend/collectors/hk_us/market_heat.py
"""Market heat data collector for HK/US stocks using yfinance."""

import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

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
    """Safely convert to float."""
    try:
        v = float(val)
        return None if math.isnan(v) else round(v, 4)
    except (TypeError, ValueError):
        return default


def _process_one(code: str, market: str, today: str) -> dict | None:
    """Fetch market heat data for a single HK/US stock."""
    try:
        symbol = _to_yf_symbol(code, market)
        ticker = yf.Ticker(symbol)

        # Get last 2 days of price history for change_pct
        start = (date.fromisoformat(today) - timedelta(days=7)).isoformat()
        hist = ticker.history(start=start, end=today)
        if hist is None or len(hist) < 2:
            return None

        close_today = float(hist["Close"].iloc[-1])
        close_prev = float(hist["Close"].iloc[-2])
        change_pct = round((close_today - close_prev) / close_prev * 100, 4) if close_prev else None

        # Get shares outstanding from .info for turnover calculation
        info = ticker.info or {}
        shares = _sf(info.get("sharesOutstanding"))
        volume = float(hist["Volume"].iloc[-1]) if len(hist) >= 1 else None

        turnover_rate = None
        if shares and volume and shares > 0:
            turnover_rate = round(volume / shares * 100, 4)

        return {
            "code": code,
            "date": today,
            "change_pct": change_pct,
            "turnover_rate": turnover_rate,
            "consecutive_limit_up": 0,
            # volume_ratio will be filled by technical collector
        }
    except Exception as e:
        logger.error(f"HK/US heat failed for {code}: {e}")
        return None


def collect_hk_us_heat(session, target_codes: dict[str, str], today: str) -> int:
    """Collect market heat data for HK/US stocks.

    Args:
        session: SQLAlchemy session.
        target_codes: dict mapping code -> market ("US" or "HK").
        today: ISO date string (YYYY-MM-DD).

    Returns:
        Number of stocks successfully collected.
    """
    if not target_codes:
        logger.warning("No target codes for HK/US heat collection")
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
                logger.info(f"HK/US Heat: {done}/{total}")

    count = 0
    for record in results:
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"HK/US Heat upsert failed for {record.get('code')}: {e}")

    session.commit()
    logger.info(f"HK/US market heat data collected: {count} stocks")
    return count
