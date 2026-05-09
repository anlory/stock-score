# backend/collectors/hk_us/universe.py
"""Sync HK/US stock universe from public sources (Wikipedia, HSI API, yfinance ETF holdings)."""

import json
import logging

import pandas as pd
import yfinance as yf

from backend.collectors.base import proxy_safe_get
from backend.database import upsert
from backend.models import Stock

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# US index constituents
# ---------------------------------------------------------------------------

def _fetch_sp500() -> list[dict]:
    """Fetch S&P 500 constituents from Wikipedia."""
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        df = tables[0]
        results = []
        for _, row in df.iterrows():
            symbol = str(row.get("Symbol", "")).strip()
            if not symbol:
                continue
            results.append({
                "code": symbol,
                "name": str(row.get("Security", symbol)),
                "industry": str(row.get("GICS Sector", "")),
                "market": "US",
                "tag": "sp500",
            })
        logger.info(f"S&P 500: {len(results)} stocks")
        return results
    except Exception as e:
        logger.error(f"Failed to fetch S&P 500: {e}")
        return []


def _fetch_nasdaq100() -> list[dict]:
    """Fetch NASDAQ 100 constituents from Wikipedia."""
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")
        # Find the table with "Ticker" column
        df = None
        for table in tables:
            cols = [str(c).lower() for c in table.columns]
            if "ticker" in cols:
                df = table
                break
        if df is None:
            logger.warning("NASDAQ 100: no table with 'Ticker' column found")
            return []

        ticker_col = next(c for c in df.columns if "ticker" in str(c).lower())
        name_col = next((c for c in df.columns if "company" in str(c).lower()), ticker_col)

        results = []
        for _, row in df.iterrows():
            symbol = str(row.get(ticker_col, "")).strip()
            if not symbol:
                continue
            results.append({
                "code": symbol,
                "name": str(row.get(name_col, symbol)),
                "industry": "",
                "market": "US",
                "tag": "nasdaq100",
            })
        logger.info(f"NASDAQ 100: {len(results)} stocks")
        return results
    except Exception as e:
        logger.error(f"Failed to fetch NASDAQ 100: {e}")
        return []


# ---------------------------------------------------------------------------
# HK index constituents
# ---------------------------------------------------------------------------

_HSI_TAGS = {
    "hsi": "HSI",
    "hstech": "HSTECH",
}

_ETF_FALLBACKS = {
    "hsi": "2800.HK",
    "hstech": "3032.HK",
}


def _fetch_hsi_api(tag: str) -> list[dict]:
    """Fetch HSI/HSTECH constituents from hsi.com.hk API."""
    url = f"https://www.hsi.com.hk/data/eng/rt/index-series/{tag}/constituents.do"
    try:
        resp = proxy_safe_get(url, timeout=15)
        data = resp.json()
        constituents = data.get("constituents", [])
        results = []
        for item in constituents:
            code_raw = str(item.get("code", "")).strip()
            if not code_raw:
                continue
            code = code_raw.zfill(5)
            results.append({
                "code": code,
                "name": str(item.get("name", code)),
                "market": "HK",
                "tag": tag,
            })
        logger.info(f"HSI API ({tag}): {len(results)} stocks")
        return results
    except Exception as e:
        logger.error(f"HSI API failed for {tag}: {e}")
        return []


def _fetch_etf_holdings(etf_symbol: str, tag: str) -> list[dict]:
    """Fallback: fetch top holdings from HK ETF via yfinance."""
    try:
        ticker = yf.Ticker(etf_symbol)
        info = ticker.info
        holdings = info.get("holdings", [])
        if not holdings:
            logger.warning(f"No holdings data for ETF {etf_symbol}")
            return []
        results = []
        for h in holdings:
            symbol = str(h.get("symbol", "")).strip()
            if not symbol:
                continue
            # yfinance HK symbols look like "0700.HK" — strip suffix, zero-pad to 5 digits
            code_raw = symbol.replace(".HK", "")
            code = code_raw.zfill(5)
            results.append({
                "code": code,
                "name": str(h.get("holdingName", code)),
                "market": "HK",
                "tag": tag,
            })
        logger.info(f"ETF holdings ({etf_symbol}): {len(results)} stocks")
        return results
    except Exception as e:
        logger.error(f"ETF holdings failed for {etf_symbol}: {e}")
        return []


def _fetch_hk_stocks() -> dict[str, dict]:
    """Fetch all HK index constituents, merging HSI and HSTECH."""
    all_stocks: dict[str, dict] = {}

    for tag, label in _HSI_TAGS.items():
        stocks = _fetch_hsi_api(tag)
        if not stocks:
            logger.warning(f"HSI API failed for {tag}, trying ETF fallback")
            etf = _ETF_FALLBACKS[tag]
            stocks = _fetch_etf_holdings(etf, tag)

        for s in stocks:
            code = s["code"]
            if code not in all_stocks:
                all_stocks[code] = {
                    "name": s["name"],
                    "market": "HK",
                    "tags": [s["tag"]],
                }
            else:
                if s["tag"] not in all_stocks[code]["tags"]:
                    all_stocks[code]["tags"].append(s["tag"])

    return all_stocks


# ---------------------------------------------------------------------------
# US stocks aggregation
# ---------------------------------------------------------------------------

def _fetch_us_stocks() -> dict[str, dict]:
    """Fetch all US index constituents, merging S&P 500 and NASDAQ 100."""
    all_stocks: dict[str, dict] = {}
    sources = [
        ("sp500", _fetch_sp500),
        ("nasdaq100", _fetch_nasdaq100),
    ]
    for tag, fetch_fn in sources:
        stocks = fetch_fn()
        for s in stocks:
            code = s["code"]
            if code not in all_stocks:
                all_stocks[code] = {
                    "name": s["name"],
                    "market": "US",
                    "industry": s.get("industry", ""),
                    "tags": [s["tag"]],
                }
            else:
                if s["tag"] not in all_stocks[code]["tags"]:
                    all_stocks[code]["tags"].append(s["tag"])
    return all_stocks


# ---------------------------------------------------------------------------
# Main sync function
# ---------------------------------------------------------------------------

def sync_hk_us_universe(session) -> int:
    """Sync HK and US stocks into the database. Returns total upserted count."""
    count = 0

    # --- US ---
    us_stocks = _fetch_us_stocks()
    for code, info in us_stocks.items():
        upsert(session, Stock, {
            "code": code,
            "name": info["name"],
            "market": info["market"],
            "industry": info.get("industry", ""),
            "index_tags": json.dumps(info.get("tags", [])),
        }, ["code"])
        count += 1
    session.commit()
    logger.info(f"US universe synced: {count} stocks")

    # --- HK ---
    hk_stocks = _fetch_hk_stocks()
    hk_count = 0
    for code, info in hk_stocks.items():
        upsert(session, Stock, {
            "code": code,
            "name": info["name"],
            "market": info["market"],
            "index_tags": json.dumps(info.get("tags", [])),
        }, ["code"])
        hk_count += 1
    session.commit()
    logger.info(f"HK universe synced: {hk_count} stocks")

    total = count + hk_count
    logger.info(f"HK/US universe synced: {total} stocks total")
    return total
