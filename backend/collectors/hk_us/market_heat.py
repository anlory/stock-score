# backend/collectors/hk_us/market_heat.py
"""Market heat data for HK/US stocks — fills turnover_rate from .info (sequential, rate-limited).

Most heat fields (change_pct, consecutive_limit_up) are already set by the technical collector.
This pass only adds turnover_rate which needs sharesOutstanding from yfinance .info.
"""

import logging
import math
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


def _sf(val, default=None):
    try:
        v = float(val)
        return None if math.isnan(v) else round(v, 4)
    except (TypeError, ValueError):
        return default


def collect_hk_us_heat(session, target_codes: dict[str, str], today: str) -> int:
    """Fill turnover_rate for HK/US stocks from yfinance .info."""
    if not target_codes:
        return 0

    count = 0
    total = len(target_codes)

    for i, (code, market) in enumerate(target_codes.items(), 1):
        try:
            symbol = _to_yf_symbol(code, market)
            info = yf.Ticker(symbol).info
            if not info:
                continue

            shares = _sf(info.get("sharesOutstanding"))
            if not shares or shares <= 0:
                continue

            # Get volume from existing daily_data (set by technical collector)
            daily = session.query(DailyData).filter(
                DailyData.code == code, DailyData.date == today,
            ).first()
            if not daily or not daily.volume_ratio:
                # Fallback: compute from recent history
                hist = yf.Ticker(symbol).history(period="5d")
                if hist is not None and len(hist) >= 1:
                    volume = float(hist["Volume"].iloc[-1])
                    turnover_rate = round(volume / shares * 100, 4)
                    upsert(session, DailyData, {
                        "code": code, "date": today,
                        "turnover_rate": turnover_rate,
                    }, ["code", "date"])
                    count += 1
                continue

            # Use volume from technical data (vol_ma5 as proxy for recent volume)
            if daily.vol_ma5:
                turnover_rate = round(daily.vol_ma5 / shares * 100, 4)
                upsert(session, DailyData, {
                    "code": code, "date": today,
                    "turnover_rate": turnover_rate,
                }, ["code", "date"])
                count += 1

        except Exception as e:
            logger.error(f"HK/US heat failed for {code}: {e}")

        if i % 20 == 0 or i == total:
            logger.info(f"HK/US Heat: {i}/{total}")
        time.sleep(_DELAY)

    session.commit()
    logger.info(f"HK/US market heat updated: {count} stocks")
    return count
