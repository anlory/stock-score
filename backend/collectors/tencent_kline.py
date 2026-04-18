"""Fetch K-line data from Tencent Finance API (gt.gtimg.cn).

Works reliably even when eastmoney/akshare APIs are blocked by proxy.
"""

import logging
import httpx

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0"}

_TENCENT_KLINE_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"


def _market_prefix(code: str) -> str:
    if code.startswith(("6", "5", "9")):
        return "sh"
    if code.startswith(("4", "8")):
        return "bj"
    return "sz"


def fetch_kline(code: str, days: int = 90, adjust: str = "qfq") -> list[dict]:
    """Return list of {date, open, close, high, low, volume} dicts."""
    prefix = _market_prefix(code)
    param = f"{prefix}{code},day,,,300,{adjust}"
    try:
        r = httpx.get(
            _TENCENT_KLINE_URL,
            params={"param": param},
            headers=_HEADERS,
            timeout=15,
            follow_redirects=True,
        )
        r.raise_for_status()
        body = r.json()
    except Exception as e:
        logger.error(f"Tencent kline failed for {code}: {e}")
        return []

    stock_data = body.get("data", {}).get(f"{prefix}{code}", {})
    key = adjust if adjust in stock_data else "qfqday"
    rows = stock_data.get(key, [])
    if not rows:
        key = "day"
        rows = stock_data.get(key, [])
    if not rows:
        return []

    result = []
    for row in rows[-days:]:
        if len(row) < 6:
            continue
        result.append({
            "date": row[0],
            "open": float(row[1]),
            "close": float(row[2]),
            "high": float(row[3]),
            "low": float(row[4]),
            "volume": float(row[5]),
        })
    return result
