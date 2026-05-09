# backend/collectors/hk_us/universe.py
"""Sync HK/US stock universe. Primary: static CSV files. Optional: live API update."""

import csv
import io
import json
import logging
from pathlib import Path

import pandas as pd

from backend.collectors.base import proxy_safe_get
from backend.database import upsert
from backend.models import Stock

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent.parent.parent.parent / "data" / "static"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

# Column name patterns for different static CSV formats
_COL_MAPS = {
    "sp500":      {"code": "Symbol",  "name": "Security",      "industry": "GICS Sector"},
    "nasdaq100":  {"code": "Symbol",  "name": "Name",          "industry": None},
    "hsi":        {"code": "code",    "name": "name",          "industry": None},
    "hstech":     {"code": "code",    "name": "name",          "industry": None},
}

_MARKET_MAP = {
    "sp500": "US", "nasdaq100": "US",
    "hsi": "HK", "hstech": "HK",
}


def _load_static_csv(tag: str) -> list[dict]:
    """Load constituents from data/static/{tag}.csv."""
    csv_path = _STATIC_DIR / f"{tag}.csv"
    if not csv_path.exists():
        logger.warning(f"Static CSV not found: {csv_path}")
        return []

    col_map = _COL_MAPS[tag]
    market = _MARKET_MAP[tag]
    results = []

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = str(row.get(col_map["code"], "")).strip()
            if not code:
                continue
            name = str(row.get(col_map["name"], code)).strip()
            industry = str(row.get(col_map["industry"], "")).strip() if col_map["industry"] else ""
            results.append({
                "code": code,
                "name": name,
                "industry": industry if industry != "nan" else "",
                "market": market,
                "tag": tag,
            })

    logger.info(f"{tag} (static): {len(results)} stocks")
    return results


def _try_update_hk_from_api(tag: str) -> list[dict] | None:
    """Optionally refresh HK constituents from HSI API. Returns None on failure."""
    url = f"https://www.hsi.com.hk/data/eng/rt/index-series/{tag}/constituents.do"
    try:
        resp = proxy_safe_get(url, headers=_HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()

        items = []
        for series in data.get("indexSeriesList", []):
            for index in series.get("indexList", []):
                items.extend(index.get("constituentContent", []))

        if not items:
            return None

        results = []
        for item in items:
            code_raw = str(item.get("code", "")).strip()
            if not code_raw:
                continue
            code = code_raw.zfill(5)
            name = str(item.get("constituentName", code))
            results.append({
                "code": code,
                "name": name,
                "market": "HK",
                "tag": tag,
            })

        # Save updated list back to static CSV
        csv_path = _STATIC_DIR / f"{tag}.csv"
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["code", "name"])
            for r in results:
                w.writerow([r["code"], r["name"]])

        logger.info(f"{tag} (API updated): {len(results)} stocks")
        return results
    except Exception as e:
        logger.debug(f"HSI API skipped for {tag}: {e}")
        return None


def _fetch_all_constituents() -> dict[str, dict]:
    """Load all constituents from static files, with optional HK API refresh."""
    all_stocks: dict[str, dict] = {}

    for tag in ("sp500", "nasdaq100", "hsi", "hstech"):
        # HK indices: try live API first to keep static file fresh
        stocks = None
        if tag in ("hsi", "hstech"):
            stocks = _try_update_hk_from_api(tag)

        # Primary: static CSV
        if not stocks:
            stocks = _load_static_csv(tag)

        for s in stocks:
            code = s["code"]
            if code not in all_stocks:
                all_stocks[code] = {
                    "name": s["name"],
                    "market": s["market"],
                    "industry": s.get("industry", ""),
                    "tags": [s["tag"]],
                }
            else:
                if s["tag"] not in all_stocks[code]["tags"]:
                    all_stocks[code]["tags"].append(s["tag"])

    return all_stocks


def sync_hk_us_universe(session) -> int:
    """Sync HK and US stocks into the database. Returns total upserted count."""
    stocks = _fetch_all_constituents()
    if not stocks:
        logger.warning("No HK/US stocks found")
        return 0

    count = 0
    for code, info in stocks.items():
        upsert(session, Stock, {
            "code": code,
            "name": info["name"],
            "market": info["market"],
            "industry": info.get("industry", ""),
            "index_tags": json.dumps(info.get("tags", [])),
        }, ["code"])
        count += 1
    session.commit()
    logger.info(f"HK/US universe synced: {count} stocks")
    return count
