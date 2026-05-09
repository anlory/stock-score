# backend/collectors/hk_us/universe.py
"""Sync HK/US stock universe from public sources (Wikipedia, HSI API, yfinance ETF holdings)."""

import io
import json
import logging

import pandas as pd
import yfinance as yf

from backend.collectors.base import proxy_safe_get
from backend.database import upsert
from backend.models import Stock

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def _read_html(url: str) -> list[pd.DataFrame]:
    """Fetch URL with proper User-Agent, return parsed HTML tables."""
    resp = proxy_safe_get(url, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    return pd.read_html(io.StringIO(resp.text))


# ---------------------------------------------------------------------------
# US index constituents
# ---------------------------------------------------------------------------

def _fetch_sp500() -> list[dict]:
    """Fetch S&P 500 constituents. Try GitHub CSV first, fall back to Wikipedia."""
    # Primary: GitHub-hosted CSV (accessible from China)
    try:
        resp = proxy_safe_get(
            "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv",
            timeout=15,
        )
        if resp.status_code == 200 and len(resp.text) > 1000:
            df = pd.read_csv(io.StringIO(resp.text))
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
            logger.info(f"S&P 500 (GitHub CSV): {len(results)} stocks")
            return results
    except Exception as e:
        logger.warning(f"S&P 500 GitHub CSV failed: {e}")

    # Fallback: Wikipedia
    try:
        tables = _read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
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
        logger.info(f"S&P 500 (Wikipedia): {len(results)} stocks")
        return results
    except Exception as e:
        logger.error(f"Failed to fetch S&P 500: {e}")
        return []


def _fetch_nasdaq100() -> list[dict]:
    """Fetch NASDAQ 100 constituents. Try Wikipedia, fall back to yfinance QQQ holdings."""
    try:
        tables = _read_html("https://en.wikipedia.org/wiki/Nasdaq-100")
        df = None
        for table in tables:
            cols = [str(c).lower() for c in table.columns]
            if "ticker" in cols:
                df = table
                break
        if df is not None:
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
            logger.info(f"NASDAQ 100 (Wikipedia): {len(results)} stocks")
            return results
    except Exception as e:
        logger.warning(f"NASDAQ 100 Wikipedia failed: {e}")

    # Fallback: yfinance QQQ ETF holdings
    import time
    try:
        time.sleep(2)
        ticker = yf.Ticker("QQQ")
        info = ticker.info
        holdings = info.get("holdings", [])
        if holdings:
            results = []
            for h in holdings:
                symbol = str(h.get("symbol", "")).strip()
                if not symbol:
                    continue
                results.append({
                    "code": symbol,
                    "name": str(h.get("holdingName", symbol)),
                    "industry": "",
                    "market": "US",
                    "tag": "nasdaq100",
                })
            logger.info(f"NASDAQ 100 (QQQ holdings): {len(results)} stocks")
            return results
    except Exception as e:
        logger.warning(f"NASDAQ 100 QQQ fallback failed: {e}")

    logger.error("All NASDAQ 100 sources failed")
    return []


def _fetch_etf_symbols(etf_symbol: str, tag: str) -> list[dict]:
    """Fetch constituent symbols from an ETF via yfinance info."""
    import time
    for attempt in range(3):
        try:
            time.sleep(3)
            info = yf.Ticker(etf_symbol).info
            holdings = info.get("holdings", [])
            if not holdings:
                logger.warning(f"No holdings for {etf_symbol} (attempt {attempt+1})")
                continue
            results = []
            for h in holdings:
                symbol = str(h.get("symbol", "")).strip()
                if not symbol:
                    continue
                results.append({
                    "code": symbol,
                    "name": str(h.get("holdingName", symbol)),
                    "industry": "",
                    "market": "US",
                    "tag": tag,
                })
            return results
        except Exception as e:
            logger.warning(f"ETF {etf_symbol} attempt {attempt+1}/3: {e}")
            time.sleep(5)
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
        resp = proxy_safe_get(url, headers=_HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"HSI API ({tag}): HTTP {resp.status_code}")
            return []
        data = resp.json()

        # Parse nested response: indexSeriesList -> indexList -> constituentContent
        items = []
        series_list = data.get("indexSeriesList", [])
        for series in series_list:
            for index in series.get("indexList", []):
                for c in index.get("constituentContent", []):
                    items.append(c)

        if not items:
            # Try flat format
            items = data.get("constituents", data.get("data", []))
        if not items and isinstance(data, list):
            items = data

        results = []
        for item in items:
            code_raw = str(item.get("code", item.get("stockCode", ""))).strip()
            if not code_raw:
                continue
            code = code_raw.zfill(5)
            name = str(item.get("constituentName",
                       item.get("name",
                       item.get("stockName",
                       item.get("engName", code)))))
            results.append({
                "code": code,
                "name": name,
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
    import time
    for attempt in range(3):
        try:
            time.sleep(2)  # Rate limit buffer
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
            logger.warning(f"ETF holdings attempt {attempt+1}/3 for {etf_symbol}: {e}")
            if attempt < 2:
                time.sleep(5)
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

    # S&P 500
    sp500 = _fetch_sp500()
    if not sp500:
        logger.warning("S&P 500 CSV/Wikipedia failed, trying SPY ETF holdings")
        sp500 = _fetch_etf_symbols("SPY", "sp500")
    logger.info(f"S&P 500: {len(sp500)} stocks")

    # NASDAQ 100
    ndx = _fetch_nasdaq100()
    if not ndx:
        logger.warning("NASDAQ 100 sources failed, trying QQQ ETF holdings")
        ndx = _fetch_etf_symbols("QQQ", "nasdaq100")
    logger.info(f"NASDAQ 100: {len(ndx)} stocks")

    for tag, stocks in [("sp500", sp500), ("nasdaq100", ndx)]:
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
