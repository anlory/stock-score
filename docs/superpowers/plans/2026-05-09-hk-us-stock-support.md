# 港美股支持 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add HK/US stock index (HSI, HSTECH, S&P 500, NASDAQ 100) constituent syncing and full scoring pipeline to the existing A-share system.

**Architecture:** Parallel collector tracks — existing A-share collectors stay untouched. New `collectors/hk_us/` module uses yfinance for data. Engine routes stocks to correct collector set based on `market` field. Percentile ranking scoped within each market.

**Tech Stack:** yfinance, pandas_ta, Wikipedia table scraping, HSI Company API

---

## File Structure

| Operation | File | Responsibility |
|-----------|------|----------------|
| Create | `backend/collectors/hk_us/__init__.py` | Module init |
| Create | `backend/collectors/hk_us/universe.py` | Fetch HSI/HSTECH/S&P500/NASDAQ100 constituents |
| Create | `backend/collectors/hk_us/technical.py` | OHLCV + pandas_ta indicators via yfinance |
| Create | `backend/collectors/hk_us/fundamental.py` | PE/PB/ROE/market cap via yfinance .info |
| Create | `backend/collectors/hk_us/market_heat.py` | Change%, turnover derived from yfinance history |
| Create | `backend/collectors/hk_us/news.py` | News count from yfinance .news (degraded) |
| Create | `backend/collectors/hk_us/profile.py` | Basic stock info via yfinance .info |
| Modify | `backend/collectors/universe.py` | Call HK/US sync alongside A-share sync |
| Modify | `backend/engine.py` | Market-aware scoring, separate percentile pools |
| Modify | `backend/routers/trigger.py` | Add HK/US collectors to pipeline |
| Modify | `backend/routers/scores.py` | Market-aware leaderboard, remove zfill(6) for non-A-share |
| Modify | `backend/services.py` | Market-aware collect_single, search |
| Modify | `backend/routers/stocks.py` | Market-aware watchlist, profile, search |
| Modify | `frontend/src/views/Dashboard.vue` | HK/US route shows index-filtered dashboard |
| Modify | `frontend/src/views/StockDetail.vue` | Multi-market code display, external links |
| Modify | `frontend/src/router/index.js` | Add index tab routes |
| Modify | `frontend/src/api/index.js` | Add market param to leaderboard API |
| Modify | `pyproject.toml` | Add yfinance dependency |

---

### Task 1: Add yfinance dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add yfinance to pyproject.toml**

Add `yfinance` to the dependencies list:

```toml
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy>=2.0.30",
    "pywencai>=0.13.1",
    "tushare>=1.2.89",
    "pandas>=2.2.0",
    "pandas-ta>=0.3.14b",
    "apscheduler>=3.10.0",
    "httpx>=0.27.0",
    "aiofiles>=23.0.0",
    "yfinance>=0.2.40",
]
```

- [ ] **Step 2: Install dependency**

Run: `uv sync`
Expected: yfinance installed successfully

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add yfinance dependency for HK/US stock data"
```

---

### Task 2: Create HK/US universe sync module

**Files:**
- Create: `backend/collectors/hk_us/__init__.py`
- Create: `backend/collectors/hk_us/universe.py`

- [ ] **Step 1: Create `__init__.py`**

```python
# backend/collectors/hk_us/__init__.py
```

- [ ] **Step 2: Create `universe.py` with constituent fetchers**

```python
import logging
import json
import pandas as pd
import yfinance as yf
from backend.collectors.base import proxy_safe_get
from backend.database import upsert
from backend.models import Stock

logger = logging.getLogger(__name__)

HK_INDICES = {
    "hsi":    {"name": "恒生指数",   "etf": "2800.HK"},
    "hstech": {"name": "恒生科技",   "etf": "3032.HK"},
}

US_INDICES = {
    "sp500":     {"name": "S&P 500",    "url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"},
    "nasdaq100": {"name": "NASDAQ 100", "url": "https://en.wikipedia.org/wiki/Nasdaq-100"},
}


def _fetch_sp500() -> list[dict]:
    """Fetch S&P 500 constituents from Wikipedia."""
    try:
        tables = pd.read_html(US_INDICES["sp500"]["url"])
        df = tables[0]
        results = []
        for _, row in df.iterrows():
            symbol = str(row.get("Symbol", "")).strip()
            name = str(row.get("Security", "")).strip()
            sector = str(row.get("GICS Sector", "")).strip()
            if symbol and name:
                results.append({"code": symbol, "name": name, "industry": sector, "tag": "sp500"})
        logger.info(f"S&P 500: {len(results)} stocks")
        return results
    except Exception as e:
        logger.error(f"S&P 500 fetch failed: {e}")
        return []


def _fetch_nasdaq100() -> list[dict]:
    """Fetch NASDAQ 100 constituents from Wikipedia."""
    try:
        tables = pd.read_html(US_INDICES["nasdaq100"]["url"])
        # Find the table with Ticker/Company columns
        df = None
        for t in tables:
            cols = [str(c).lower() for c in t.columns]
            if any("ticker" in c for c in cols):
                df = t
                break
        if df is None:
            df = tables[4] if len(tables) > 4 else tables[0]

        ticker_col = next((c for c in df.columns if "ticker" in str(c).lower()), df.columns[0])
        company_col = next((c for c in df.columns if "company" in str(c).lower()), df.columns[1])
        sector_col = next((c for c in df.columns if "sector" in str(c).lower() or "industry" in str(c).lower()), None)

        results = []
        for _, row in df.iterrows():
            symbol = str(row.get(ticker_col, "")).strip()
            name = str(row.get(company_col, "")).strip()
            if symbol and name and symbol != "nan" and name != "nan":
                industry = str(row.get(sector_col, "")).strip() if sector_col else ""
                results.append({"code": symbol, "name": name, "industry": industry if industry != "nan" else "", "tag": "nasdaq100"})
        logger.info(f"NASDAQ 100: {len(results)} stocks")
        return results
    except Exception as e:
        logger.error(f"NASDAQ 100 fetch failed: {e}")
        return []


def _fetch_hk_constituents() -> list[dict]:
    """Fetch HSI and HSTECH constituents from Hang Seng Indexes Company API."""
    results = []
    for tag, info in HK_INDICES.items():
        try:
            url = f"https://www.hsi.com.hk/data/eng/rt/index-series/{tag}/constituents.do"
            r = proxy_safe_get(url, timeout=15)
            if r.status_code != 200:
                logger.warning(f"HSI API returned {r.status_code} for {tag}")
                continue
            data = r.json()
            constituents = data.get("constituents", data.get("data", []))
            if not constituents:
                logger.warning(f"No constituents data for {info['name']}")
                continue
            for item in constituents:
                code = str(item.get("code", "")).strip()
                name = str(item.get("name", "")).strip()
                if code and name:
                    results.append({
                        "code": code.zfill(5),
                        "name": name,
                        "industry": "",
                        "tag": tag,
                    })
            logger.info(f"{info['name']}: {len([r for r in results if r['tag'] == tag])} stocks")
        except Exception as e:
            logger.error(f"{info['name']} fetch failed: {e}")
    return results


def _fetch_hk_constituents_fallback() -> list[dict]:
    """Fallback: fetch HK constituents from yfinance ETF top holdings."""
    results = []
    for tag, info in HK_INDICES.items():
        try:
            ticker = yf.Ticker(info["etf"])
            holdings = ticker.info.get("holdings", [])
            if not holdings:
                # Try institutional_holders as last resort
                logger.warning(f"No holdings for {info['name']}, using ETF price as proxy")
                continue
            for h in holdings:
                symbol = str(h.get("symbol", h.get("holdingName", ""))).strip()
                name = str(h.get("holdingName", h.get("symbol", ""))).strip()
                if symbol:
                    # yfinance returns HK codes like 0700.HK
                    code = symbol.split(".")[0].zfill(5) if ".HK" in symbol else symbol
                    results.append({"code": code, "name": name, "industry": "", "tag": tag})
            logger.info(f"{info['name']} (fallback): {len([r for r in results if r['tag'] == tag])} stocks")
        except Exception as e:
            logger.error(f"{info['name']} fallback failed: {e}")
    return results


def fetch_hk_us_constituents() -> dict[str, dict]:
    """Fetch all HK/US index constituents. Returns {code: {name, market, industry, tags}}."""
    all_stocks: dict[str, dict] = {}

    # US stocks
    for fetcher in [_fetch_sp500, _fetch_nasdaq100]:
        for item in fetcher():
            code = item["code"]
            if code not in all_stocks:
                all_stocks[code] = {
                    "name": item["name"],
                    "market": "US",
                    "industry": item.get("industry", ""),
                    "tags": [item["tag"]],
                }
            else:
                if item["tag"] not in all_stocks[code]["tags"]:
                    all_stocks[code]["tags"].append(item["tag"])

    # HK stocks: try HSI API first, fallback to yfinance
    hk_stocks = _fetch_hk_constituents()
    if not hk_stocks:
        logger.warning("HSI API failed, trying yfinance fallback for HK stocks")
        hk_stocks = _fetch_hk_constituents_fallback()

    for item in hk_stocks:
        code = item["code"]
        if code not in all_stocks:
            all_stocks[code] = {
                "name": item["name"],
                "market": "HK",
                "industry": item.get("industry", ""),
                "tags": [item["tag"]],
            }
        else:
            if item["tag"] not in all_stocks[code]["tags"]:
                all_stocks[code]["tags"].append(item["tag"])

    logger.info(f"HK/US universe: {len(all_stocks)} stocks total")
    return all_stocks


def sync_hk_us_universe(session) -> int:
    """Sync HK/US index constituents to database. Returns count of stocks synced."""
    stocks = fetch_hk_us_constituents()
    if not stocks:
        logger.warning("No HK/US stocks fetched")
        return 0

    count = 0
    for code, info in stocks.items():
        upsert(session, Stock, {
            "code": code,
            "name": info["name"],
            "market": info["market"],
            "industry": info.get("industry", ""),
            "is_watchlist": False,
            "index_tags": json.dumps(info.get("tags", [])),
        }, ["code"])
        count += 1
    session.commit()
    logger.info(f"HK/US universe synced: {count} stocks")
    return count
```

- [ ] **Step 3: Verify the module imports**

Run: `uv run python -c "from backend.collectors.hk_us.universe import fetch_hk_us_constituents; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/collectors/hk_us/__init__.py backend/collectors/hk_us/universe.py
git commit -m "feat: add HK/US universe sync (HSI, HSTECH, S&P500, NASDAQ100)"
```

---

### Task 3: Create HK/US technical collector

**Files:**
- Create: `backend/collectors/hk_us/technical.py`

- [ ] **Step 1: Create the technical collector**

This mirrors the A-share `collectors/technical.py` but uses yfinance as the data source. It produces the same `DailyData` fields so scorers work without modification.

```python
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import pandas as pd
import pandas_ta as ta
import yfinance as yf

from backend.database import upsert
from backend.models import DailyData, Stock

logger = logging.getLogger(__name__)
_MAX_WORKERS = 5  # yfinance is slower, fewer workers


def _yf_code(code: str, market: str) -> str:
    """Convert DB code to yfinance ticker format."""
    if market == "HK":
        return f"{int(code):04d}.HK"
    return code  # US tickers used as-is


def _compute_returns(closes: list[float]) -> dict:
    out = {"return_5d": None, "return_20d": None, "return_60d": None,
           "return_3d": None, "return_13d": None, "return_mid": None}
    today_c = closes[-1] if closes else None
    for window, key in [(3, "return_3d"), (5, "return_5d"), (13, "return_13d"),
                        (20, "return_20d"), (60, "return_60d")]:
        if today_c and len(closes) > window and closes[-window - 1]:
            out[key] = round((today_c - closes[-window - 1]) / closes[-window - 1] * 100, 2)
    if len(closes) > 31 and closes[-31] and closes[-6]:
        out["return_mid"] = round((closes[-6] - closes[-31]) / closes[-31] * 100, 2)
    return out


def _detect_patterns(last_row, prev_row, change_pct) -> list[str]:
    tags = []
    ma5 = _f(last_row, "SMA_5"); ma13 = _f(last_row, "SMA_13")
    pma5 = _f(prev_row, "SMA_5"); pma13 = _f(prev_row, "SMA_13")
    if None not in (ma5, ma13, pma5, pma13):
        if ma5 > ma13 and pma5 < pma13:
            tags.append("MA5上穿MA13")
        elif ma5 < ma13 and pma5 > pma13:
            tags.append("MA5下穿MA13")
    dif = _f(last_row, "MACD_12_26_9"); dea = _f(last_row, "MACDs_12_26_9")
    pdif = _f(prev_row, "MACD_12_26_9"); pdea = _f(prev_row, "MACDs_12_26_9")
    if None not in (dif, dea, pdif, pdea):
        if dif > dea and pdif <= pdea:
            tags.append("MACD金叉")
    return tags


def _process_one(code: str, market: str, today: str) -> dict | None:
    try:
        ticker = _yf_code(code, market)
        hist = yf.Ticker(ticker).history(period="6mo")
        if hist is None or len(hist) < 15:
            return None

        df = hist.reset_index()
        df = df.rename(columns={"Date": "date", "Open": "open", "High": "high",
                                 "Low": "low", "Close": "close", "Volume": "volume"})
        df = df.sort_values("date").reset_index(drop=True)

        # Apply pandas_ta indicators (same as A-share)
        df.ta.sma(length=5, append=True)
        df.ta.sma(length=13, append=True)
        df.ta.sma(length=30, append=True)
        df.ta.macd(append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.kdj(append=True)
        df.ta.bbands(length=20, append=True)

        df["VOL_MA5"] = df["volume"].rolling(5).mean()
        df["VOL_RATIO"] = df["volume"] / df["VOL_MA5"]

        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last

        closes = df["close"].astype(float).tolist()
        volumes = df["volume"].astype(float).tolist()
        change_pct = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2) if len(closes) >= 2 and closes[-2] else None
        returns = _compute_returns(closes)
        tags = _detect_patterns(last, prev, change_pct)

        vol_ma3 = sum(volumes[-3:]) / 3 if len(volumes) >= 3 else None
        vol_ma5 = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else None
        vol_ma13 = sum(volumes[-13:]) / 13 if len(volumes) >= 13 else None
        vol_ma30 = sum(volumes[-30:]) / 30 if len(volumes) >= 30 else None

        close_today = closes[-1]
        is_30d_high = 1 if close_today >= max(closes[-30:]) and len(closes) >= 30 else 0
        is_10d_high = 1 if close_today >= max(closes[-10:]) and len(closes) >= 10 else 0

        ma5_vals = [df.iloc[i].get("SMA_5") for i in range(-4, 0)]
        ma5_slope3 = None
        if all(pd.notna(v) for v in ma5_vals) and ma5_vals[0] and ma5_vals[0] > 0:
            ma5_slope3 = round((float(ma5_vals[3]) - float(ma5_vals[0])) / float(ma5_vals[0]) * 100, 4)

        close_above_ma5_5d = 0
        for i in range(-5, 0):
            c = closes[i]
            m = _f(df.iloc[i], "SMA_5")
            if m is not None and c >= m:
                close_above_ma5_5d += 1

        ma5_today = _f(last, "SMA_5")
        last_close_above_ma5 = 1 if ma5_today is not None and close_today >= ma5_today else 0

        return {
            "code": code,
            "date": today,
            "close": _f(last, "close"),
            "change_pct": change_pct,
            "ma5": _f(last, "SMA_5"),
            "ma13": _f(last, "SMA_13"),
            "ma30": _f(last, "SMA_30"),
            "prev_ma5": _f(prev, "SMA_5"),
            "prev_ma13": _f(prev, "SMA_13"),
            "prev_ma30": _f(prev, "SMA_30"),
            "macd_dif": _f(last, "MACD_12_26_9"),
            "macd_dea": _f(last, "MACDs_12_26_9"),
            "macd_bar": _f(last, "MACDh_12_26_9"),
            "rsi14": _f(last, "RSI_14"),
            "kdj_k": _f(last, "K_9_3"),
            "kdj_d": _f(last, "D_9_3"),
            "kdj_j": _f(last, "J_9_3"),
            "boll_upper": _f(last, "BBU_20_2.0") or _f(last, "BBU_20_2.0_2.0"),
            "boll_mid": _f(last, "BBM_20_2.0") or _f(last, "BBM_20_2.0_2.0"),
            "boll_lower": _f(last, "BBL_20_2.0") or _f(last, "BBL_20_2.0_2.0"),
            "volume_ratio": _f(last, "VOL_RATIO"),
            **returns,
            "vol_ma3": round(vol_ma3, 2) if vol_ma3 else None,
            "vol_ma5": round(vol_ma5, 2) if vol_ma5 else None,
            "vol_ma13": round(vol_ma13, 2) if vol_ma13 else None,
            "vol_ma30": round(vol_ma30, 2) if vol_ma30 else None,
            "is_30d_high": is_30d_high,
            "is_10d_high": is_10d_high,
            "ma5_slope3": ma5_slope3,
            "close_above_ma5_5d": close_above_ma5_5d,
            "last_close_above_ma5": last_close_above_ma5,
            "pattern_tags": json.dumps(tags, ensure_ascii=False),
        }
    except Exception as e:
        logger.error(f"HK/US technical failed for {code}: {e}")
        return None


def collect_hk_us_technical(session, target_codes: dict[str, str] = None, today: str = None) -> int:
    """Collect technical data for HK/US stocks.
    target_codes: {code: market} mapping, e.g. {"AAPL": "US", "00700": "HK"}
    """
    today = today or date.today().isoformat()
    if not target_codes:
        return 0

    codes = sorted(target_codes.keys())
    results = []
    done = 0
    total = len(codes)

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {
            pool.submit(_process_one, code, target_codes[code], today): code
            for code in codes
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
            done += 1
            if done % 50 == 0 or done == total:
                logger.info(f"HK/US Technical: {done}/{total}")

    count = 0
    for record in results:
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"HK/US Technical upsert failed for {record.get('code')}: {e}")

    session.commit()
    logger.info(f"HK/US Technical data collected: {count} stocks")
    return count


def _f(row, col):
    val = row.get(col)
    try:
        return round(float(val), 4) if pd.notna(val) else None
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 2: Verify import**

Run: `uv run python -c "from backend.collectors.hk_us.technical import collect_hk_us_technical; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/collectors/hk_us/technical.py
git commit -m "feat: add HK/US technical collector using yfinance"
```

---

### Task 4: Create HK/US fundamental collector

**Files:**
- Create: `backend/collectors/hk_us/fundamental.py`

- [ ] **Step 1: Create the fundamental collector**

```python
import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import yfinance as yf

from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)
_MAX_WORKERS = 5


def _yf_code(code: str, market: str) -> str:
    if market == "HK":
        return f"{int(code):04d}.HK"
    return code


def _fetch_one(code: str, market: str, today: str) -> dict | None:
    try:
        ticker = yf.Ticker(_yf_code(code, market))
        info = ticker.info
        if not info:
            return None

        record = {"code": code, "date": today}

        # PE / PB
        record["pe"] = _sf(info.get("trailingPE"))
        record["pb"] = _sf(info.get("priceToBook"))

        # Market cap (convert to 亿元)
        raw_mv = info.get("marketCap")
        if raw_mv:
            record["market_cap"] = round(raw_mv / 1e8, 4)

        # ROE
        record["roe"] = _sf(info.get("returnOnEquity"))
        if record["roe"] is not None:
            record["roe"] = round(record["roe"] * 100, 4)  # convert ratio to %

        # Profit growth YoY
        record["profit_growth_yoy"] = _sf(info.get("earningsGrowth"))
        if record["profit_growth_yoy"] is not None:
            record["profit_growth_yoy"] = round(record["profit_growth_yoy"] * 100, 4)

        # Only return if we got at least one meaningful field
        has_data = any(record.get(k) is not None for k in ("pe", "pb", "roe", "market_cap"))
        return record if has_data else None
    except Exception as e:
        logger.error(f"HK/US fundamental failed for {code}: {e}")
        return None


def collect_hk_us_fundamental(session, target_codes: dict[str, str] = None, today: str = None) -> int:
    """Collect fundamental data for HK/US stocks.
    target_codes: {code: market} mapping
    """
    today = today or date.today().isoformat()
    if not target_codes:
        return 0

    codes = sorted(target_codes.keys())
    results = []
    done = 0
    total = len(codes)

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {
            pool.submit(_fetch_one, code, target_codes[code], today): code
            for code in codes
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
            done += 1
            if done % 50 == 0 or done == total:
                logger.info(f"HK/US Fundamental: {done}/{total}")

    count = 0
    for record in results:
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"HK/US Fundamental upsert failed for {record.get('code')}: {e}")

    session.commit()
    logger.info(f"HK/US Fundamental data collected: {count} stocks")
    return count


def _sf(val, default=None):
    try:
        v = float(val)
        return None if math.isnan(v) else round(v, 4)
    except (TypeError, ValueError):
        return default
```

- [ ] **Step 2: Commit**

```bash
git add backend/collectors/hk_us/fundamental.py
git commit -m "feat: add HK/US fundamental collector using yfinance .info"
```

---

### Task 5: Create HK/US market heat + news collectors

**Files:**
- Create: `backend/collectors/hk_us/market_heat.py`
- Create: `backend/collectors/hk_us/news.py`
- Create: `backend/collectors/hk_us/profile.py`

- [ ] **Step 1: Create market_heat.py**

```python
import logging
import math
from datetime import date

import yfinance as yf

from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)


def _yf_code(code: str, market: str) -> str:
    if market == "HK":
        return f"{int(code):04d}.HK"
    return code


def _compute_heat(code: str, market: str, today: str) -> dict | None:
    try:
        ticker = yf.Ticker(_yf_code(code, market))
        hist = ticker.history(period="1mo")
        if hist is None or hist.empty:
            return None

        df = hist.reset_index().sort_values("Date")
        if len(df) < 2:
            return None

        last = df.iloc[-1]
        prev = df.iloc[-2]

        close = float(last["Close"])
        prev_close = float(prev["Close"])
        change_pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else None

        # Turnover: yfinance doesn't give shares outstanding in history,
        # but .info has sharesOutstanding. Volume / sharesOutstanding approximates turnover.
        volume = float(last["Volume"]) if last["Volume"] else 0
        info = ticker.info or {}
        shares = info.get("sharesOutstanding") or info.get("floatShares")
        turnover_rate = round(volume / shares * 100, 4) if shares and volume else None

        return {
            "code": code,
            "date": today,
            "change_pct": change_pct,
            "turnover_rate": turnover_rate,
            "consecutive_limit_up": 0,  # N/A for HK/US
            "volume_ratio": None,  # Will be filled by technical collector
        }
    except Exception as e:
        logger.error(f"HK/US heat failed for {code}: {e}")
        return None


def collect_hk_us_heat(session, target_codes: dict[str, str] = None, today: str = None) -> int:
    today = today or date.today().isoformat()
    if not target_codes:
        return 0

    count = 0
    codes = sorted(target_codes.keys())
    total = len(codes)
    for i, code in enumerate(codes, 1):
        result = _compute_heat(code, target_codes[code], today)
        if result:
            try:
                upsert(session, DailyData, result, ["code", "date"])
                count += 1
            except Exception as e:
                logger.error(f"HK/US Heat upsert failed for {code}: {e}")
        if i % 50 == 0 or i == total:
            logger.info(f"HK/US Heat: {i}/{total}")

    session.commit()
    logger.info(f"HK/US Market heat collected: {count} stocks")
    return count
```

- [ ] **Step 2: Create news.py**

```python
import logging
from datetime import date

import yfinance as yf

from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)


def _yf_code(code: str, market: str) -> str:
    if market == "HK":
        return f"{int(code):04d}.HK"
    return code


def collect_hk_us_news(session, target_codes: dict[str, str] = None, today: str = None) -> int:
    """Collect news count for HK/US stocks (degraded vs A-share)."""
    today = today or date.today().isoformat()
    if not target_codes:
        return 0

    count = 0
    codes = sorted(target_codes.keys())
    total = len(codes)
    for i, code in enumerate(codes, 1):
        try:
            ticker = yf.Ticker(_yf_code(code, target_codes[code]))
            news = ticker.news or []
            record = {
                "code": code,
                "date": today,
                "report_count": len(news) if news else 0,
            }
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"HK/US news failed for {code}: {e}")
        if i % 50 == 0 or i == total:
            logger.info(f"HK/US News: {i}/{total}")

    session.commit()
    logger.info(f"HK/US News collected: {count} stocks")
    return count
```

- [ ] **Step 3: Create profile.py for HK/US stocks**

```python
import logging
import json
from datetime import datetime, timedelta

import yfinance as yf

from backend.models import Stock

logger = logging.getLogger(__name__)
CACHE_TTL_DAYS = 30


def _yf_code(code: str, market: str) -> str:
    if market == "HK":
        return f"{int(code):04d}.HK"
    return code


def fetch_hk_us_profile(session, code: str) -> Stock | None:
    """Fetch and update profile for a HK/US stock from yfinance."""
    stock = session.get(Stock, code)
    if not stock:
        return None

    if stock.profile_updated_at and stock.profile_updated_at > datetime.now() - timedelta(days=CACHE_TTL_DAYS):
        return stock

    market = stock.market
    try:
        info = yf.Ticker(_yf_code(code, market)).info
        if not info:
            return stock

        if info.get("longName") or info.get("shortName"):
            stock.name = info.get("longName") or info.get("shortName") or stock.name

        if info.get("sector"):
            stock.industry = info.get("sector", "")

        if info.get("longBusinessSummary"):
            stock.introduction = info.get("longBusinessSummary", "")[:500]

        if info.get("marketCap"):
            stock.total_mv = round(info["marketCap"] / 1e8, 2)

        shares = info.get("sharesOutstanding")
        if shares:
            stock.total_share = round(shares / 1e8, 4)

        if info.get("trailingPE"):
            stock.pe = round(float(info["trailingPE"]), 2)

        if info.get("priceToBook"):
            stock.pb = round(float(info["priceToBook"]), 4)

        if info.get("website"):
            stock.website = info["website"]

        if info.get("city") or info.get("country"):
            stock.city = info.get("city", "")
            stock.province = info.get("country", "")

        stock.profile_updated_at = datetime.now()
        session.commit()
    except Exception as e:
        logger.warning(f"HK/US profile failed for {code}: {e}")

    return stock
```

- [ ] **Step 4: Commit**

```bash
git add backend/collectors/hk_us/market_heat.py backend/collectors/hk_us/news.py backend/collectors/hk_us/profile.py
git commit -m "feat: add HK/US market heat, news, and profile collectors"
```

---

### Task 6: Modify engine.py for market-aware scoring

**Files:**
- Modify: `backend/engine.py`

- [ ] **Step 1: Update engine.py to handle market-specific scoring**

The key changes:
1. Separate percentile pools by market (A-share vs HK/US)
2. HK/US stocks get 0 for capital_score (no data)
3. Strategies auto-redistribute capital weight for HK/US

Replace the full file content of `backend/engine.py`:

```python
import logging
from datetime import date
from backend.scorers.technical import TechnicalScorer
from backend.scorers.capital import CapitalScorer
from backend.scorers.fundamental import FundamentalScorer
from backend.scorers.news import NewsScorer
from backend.scorers.market_heat import HeatScorer
from backend.scorers.setup import SetupScorer
from backend.database import upsert
from backend.models import Score, Strategy, DailyData, Stock

logger = logging.getLogger(__name__)

_A_SHARE_MARKETS = {"SH", "SZ", "BJ"}


class ScoreEngine:
    def __init__(self):
        self.technical = TechnicalScorer()
        self.capital = CapitalScorer()
        self.fundamental = FundamentalScorer()
        self.news = NewsScorer()
        self.heat = HeatScorer()
        self.setup = SetupScorer()

    def _build_universe_stats(self, records: list) -> dict:
        fields = [
            "main_inflow_today", "main_inflow_5d", "super_large_inflow",
            "pe", "pb", "roe", "profit_growth_yoy", "change_pct", "turnover_rate",
        ]
        stats = {f: [] for f in fields}
        for r in records:
            d = r if isinstance(r, dict) else r.__dict__
            for f in fields:
                v = d.get(f)
                if v is not None:
                    try:
                        stats[f].append(float(v))
                    except (TypeError, ValueError):
                        pass
        return stats

    def _dimension_scores(self, data, universe: list) -> dict:
        stats = self._build_universe_stats(universe)
        d = data if isinstance(data, dict) else data.__dict__

        market = d.get("market", "")
        is_hk_us = market not in _A_SHARE_MARKETS

        dims = {
            "technical_score": self.technical.score(d),
            "capital_score": 0.0 if is_hk_us else self.capital.score(d, stats),
            "fundamental_score": self.fundamental.score(d, stats),
            "news_score": self.news.score(d),
            "heat_score": self.heat.score(d, stats),
            "setup_score": self.setup.score(d, stats),
        }
        return dims

    def _redistribute_weights(self, strategy, market: str) -> dict:
        """For HK/US stocks, redistribute capital_weight to technical and fundamental."""
        weights = {
            "technical": strategy.technical_weight,
            "capital": strategy.capital_weight,
            "fundamental": strategy.fundamental_weight,
            "news": strategy.news_weight,
            "heat": strategy.heat_weight,
            "setup": getattr(strategy, "setup_weight", 0),
        }
        if market in _A_SHARE_MARKETS:
            return weights

        # Redistribute capital weight: half to technical, half to fundamental
        cap_w = weights["capital"]
        weights["technical"] += cap_w * 0.5
        weights["fundamental"] += cap_w * 0.5
        weights["capital"] = 0.0
        return weights

    def _calc_total(self, dims: dict, strategy, market: str) -> float:
        w = self._redistribute_weights(strategy, market)
        return (
            dims["technical_score"] * w["technical"] +
            dims["capital_score"] * w["capital"] +
            dims["fundamental_score"] * w["fundamental"] +
            dims["news_score"] * w["news"] +
            dims["heat_score"] * w["heat"] +
            dims["setup_score"] * w["setup"]
        )

    def score_stock(self, data, universe: list, strategy) -> dict:
        dims = self._dimension_scores(data, universe)
        d = data if isinstance(data, dict) else data.__dict__
        market = d.get("market", "SH")
        total = self._calc_total(dims, strategy, market)
        return {**dims, "total_score": round(total, 2)}

    def run(self, session, today: str = None):
        today = today or date.today().isoformat()
        records = session.query(DailyData).filter(DailyData.date == today).all()
        if not records:
            logger.warning(f"No daily data for {today}")
            return 0

        # Load market info for all stocks
        codes = [r.code for r in records]
        stocks = {s.code: s for s in session.query(Stock).filter(Stock.code.in_(codes))}

        # Build separate universe pools by market type
        a_share_records = []
        hk_us_records = []
        for r in records:
            s = stocks.get(r.code)
            market = s.market if s else "SH"
            if market in _A_SHARE_MARKETS:
                a_share_records.append(r.__dict__)
            else:
                # Attach market to record for scorer access
                rd = r.__dict__
                rd["market"] = market
                hk_us_records.append(rd)

        strategies = session.query(Strategy).all()
        scored = 0

        for record in records:
            s = stocks.get(record.code)
            market = s.market if s else "SH"
            universe = a_share_records if market in _A_SHARE_MARKETS else hk_us_records

            dims = self._dimension_scores(record, universe)
            for strategy in strategies:
                total = self._calc_total(dims, strategy, market)
                score_record = {
                    "code": record.code, "date": today, "strategy": strategy.name,
                    "technical_score": dims["technical_score"],
                    "capital_score": dims["capital_score"],
                    "fundamental_score": dims["fundamental_score"],
                    "news_score": dims["news_score"],
                    "heat_score": dims["heat_score"],
                    "setup_score": dims["setup_score"],
                    "total_score": round(total, 2),
                }
                upsert(session, Score, score_record, ["code", "date", "strategy"])
                scored += 1

        session.commit()
        logger.info(f"Scoring complete: {scored} records")
        return scored
```

- [ ] **Step 2: Verify engine imports**

Run: `uv run python -c "from backend.engine import ScoreEngine; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/engine.py
git commit -m "feat: market-aware scoring engine with separate percentile pools"
```

---

### Task 7: Integrate HK/US into pipeline

**Files:**
- Modify: `backend/collectors/universe.py`
- Modify: `backend/routers/trigger.py`

- [ ] **Step 1: Update `universe.py` to call HK/US sync**

Add the import and call at the end of `sync_universe()`, right before the stale stock removal. Find this block:

```python
    session.commit()

    # 4. Remove stale stocks not in index and not watchlisted
```

Insert HK/US sync before it. The full change: add import at top and call in `sync_universe`:

At the top of `universe.py`, add after existing imports:
```python
from backend.collectors.hk_us.universe import sync_hk_us_universe
```

In `sync_universe()`, after the A-share watchlist section and commit, add HK/US sync:

```python
    # 3.5 HK/US index sync
    try:
        hk_us_count = sync_hk_us_universe(session)
        logger.info(f"HK/US sync: {hk_us_count} stocks")
    except Exception as e:
        logger.error(f"HK/US universe sync failed: {e}")
```

Insert this block right before the `# 4. Remove stale stocks` comment.

Also update the stale removal logic to not remove HK/US stocks. Find:

```python
    # 4. Remove stale stocks not in index and not watchlisted
    valid_codes = set(index_stocks.keys())
```

Change to:
```python
    # 4. Remove stale A-share stocks not in index and not watchlisted
    valid_codes = set(index_stocks.keys())
    # Also keep all HK/US stocks (they have their own sync lifecycle)
    hk_us_stocks = session.query(Stock).filter(
        ~Stock.market.in_(["SH", "SZ", "BJ"])
    ).all()
    valid_codes.update(s.code for s in hk_us_stocks)
```

- [ ] **Step 2: Update `trigger.py` to run HK/US collectors**

Add imports at the top of `trigger.py`:

```python
from backend.collectors.hk_us.technical import collect_hk_us_technical
from backend.collectors.hk_us.fundamental import collect_hk_us_fundamental
from backend.collectors.hk_us.market_heat import collect_hk_us_heat
from backend.collectors.hk_us.news import collect_hk_us_news
```

In `_run_collect()`, after the A-share collector section (after `for future in as_completed(futures):` block ends), add HK/US collection:

```python
        # HK/US stock collection
        hk_us_stocks = session.query(Stock).filter(
            ~Stock.market.in_(["SH", "SZ", "BJ"])
        ).all()
        if hk_us_stocks:
            hk_us_codes = {s.code: s.market for s in hk_us_stocks}
            session.close()

            logger.info(f"[Collect] HK/US: {len(hk_us_codes)} stocks")

            hk_us_collectors = [
                ("hk_us_technical", lambda s, c, t: collect_hk_us_technical(s, hk_us_codes, t)),
                ("hk_us_fundamental", lambda s, c, t: collect_hk_us_fundamental(s, hk_us_codes, t)),
                ("hk_us_heat", lambda s, c, t: collect_hk_us_heat(s, hk_us_codes, t)),
                ("hk_us_news", lambda s, c, t: collect_hk_us_news(s, hk_us_codes, t)),
            ]

            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = {
                    pool.submit(_run_collector, name, fn, None, trade_date): name
                    for name, fn in hk_us_collectors
                }
                for future in as_completed(futures):
                    name, count, err = future.result()
                    if err:
                        logger.error(f"HK/US collector {name} failed: {err}")
```

Note: The `_run_collector` function passes `codes` to the collector functions. For HK/US collectors, we use `hk_us_codes` directly in the lambda closures, so the `codes` parameter from `_run_collector` is ignored (we pass `None`).

- [ ] **Step 3: Verify trigger imports**

Run: `uv run python -c "from backend.routers.trigger import router; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/collectors/universe.py backend/routers/trigger.py
git commit -m "feat: integrate HK/US collectors into pipeline and universe sync"
```

---

### Task 8: Market-aware services and API routes

**Files:**
- Modify: `backend/services.py`
- Modify: `backend/routers/stocks.py`
- Modify: `backend/routers/scores.py`

- [ ] **Step 1: Update `services.py` for multi-market support**

The `collect_single` function needs to detect market and route to the right collectors. Replace the `collect_single` function:

```python
def collect_single(code: str) -> dict:
    """Collect data and score for a single stock. Returns status dict."""
    session = get_db_session()
    try:
        stock = session.query(Stock).get(code)
        if not stock:
            return {"status": "error", "message": "Stock not in database"}

        market = stock.market
        is_hk_us = market not in ("SH", "SZ", "BJ")

        if is_hk_us:
            from backend.collectors.hk_us.profile import fetch_hk_us_profile
            from backend.collectors.hk_us.technical import collect_hk_us_technical
            from backend.collectors.hk_us.fundamental import collect_hk_us_fundamental
            from backend.collectors.hk_us.market_heat import collect_hk_us_heat
            from backend.collectors.hk_us.news import collect_hk_us_news

            target_map = {code: market}
            try:
                fetch_hk_us_profile(session, code)
            except Exception as e:
                logger.warning(f"HK/US profile collect failed for {code}: {e}")

            collectors = [
                ("technical", lambda s, c, t: collect_hk_us_technical(s, target_map, t)),
                ("fundamental", lambda s, c, t: collect_hk_us_fundamental(s, target_map, t)),
                ("heat", lambda s, c, t: collect_hk_us_heat(s, target_map, t)),
                ("news", lambda s, c, t: collect_hk_us_news(s, target_map, t)),
            ]
        else:
            code = code.zfill(6)
            from backend.collectors.profile import fetch_profile
            try:
                fetch_profile(session, code)
            except Exception as e:
                logger.warning(f"profile collect failed for {code}: {e}")

            target = {code}
            from backend.collectors.technical import collect_technical
            from backend.collectors.capital import collect_capital
            from backend.collectors.fundamental import collect_fundamental
            from backend.collectors.news import collect_news
            from backend.collectors.market_heat import collect_market_heat

            collectors = [
                ("technical", collect_technical),
                ("capital", collect_capital),
                ("fundamental", collect_fundamental),
                ("news", collect_news),
                ("market_heat", collect_market_heat),
            ]

        for name, fn in collectors:
            try:
                if is_hk_us:
                    fn(session, None, None)
                else:
                    fn(session, target)
            except Exception as e:
                logger.warning(f"[{name}] collect failed for {code}: {e}")

        from backend.models import DailyData, Score, Strategy
        from backend.engine import ScoreEngine

        today = datetime.now().strftime("%Y-%m-%d")
        records = session.query(DailyData).filter(DailyData.code == code, DailyData.date == today).all()
        if records:
            universe = [r.__dict__ for r in records]
            # Attach market info for scoring
            for r in universe:
                if "market" not in r:
                    r["market"] = market
            engine = ScoreEngine()
            strategies = session.query(Strategy).all()
            for strategy in strategies:
                scores = engine.score_stock(records[0], universe, strategy)
                upsert(session, Score, {
                    "code": code, "date": today, "strategy": strategy.name,
                    **scores,
                }, ["code", "date", "strategy"])
            session.commit()

        return {"status": "done", "code": code}
    except Exception as e:
        logger.error(f"Single collect failed for {code}: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        session.close()
```

Also update `search_stock` to support HK/US codes:

```python
def search_stock(q: str, session) -> list[dict]:
    """Search local DB by code or name."""
    q = q.strip()
    if not q:
        return []
    local = session.query(Stock).filter(
        (Stock.code.contains(q)) | (Stock.name.contains(q))
    ).limit(10).all()
    if local:
        return [{"code": s.code, "name": s.name, "market": s.market} for s in local]
    # Fallback: try Tencent for A-share codes only
    if len(q) <= 6 and q.isdigit():
        result = fetch_stock_from_tencent(q)
        if result:
            upsert(session, Stock, {
                "code": result["code"], "name": result["name"],
                "market": result["market"], "is_watchlist": False, "index_tags": "[]",
            }, ["code"])
            session.commit()
            return [result]
    return []
```

- [ ] **Step 2: Update `routers/stocks.py` — watchlist and profile for multi-market**

In `add_to_watchlist`, remove the hardcoded market detection. Replace the function:

```python
@router.post("/watchlist")
def add_to_watchlist(stock: StockIn, session: Session = Depends(get_session)):
    from backend.services import fetch_stock_from_tencent
    code = stock.code
    existing = session.get(Stock, code)
    if existing:
        existing.is_watchlist = True
        if stock.name:
            existing.name = stock.name
        session.commit()
        return {"code": code, "name": existing.name}

    name = stock.name
    market = "SZ"

    # Try to detect market from code format
    if code.isdigit():
        code = code.zfill(6)
        if code.startswith(("6", "5", "9")):
            market = "SH"
        elif code.startswith(("4", "8")):
            market = "BJ"
        else:
            market = "SZ"
        if not name:
            info = fetch_stock_from_tencent(code)
            name = info["name"] if info else code
    else:
        # Non-numeric code (US ticker like AAPL)
        market = "US"
        if not name:
            name = code

    upsert(session, Stock, {
        "code": code, "name": name,
        "market": market, "is_watchlist": True, "index_tags": "[]",
    }, ["code"])
    session.commit()
    return {"code": code, "name": name}
```

Update `get_stock_profile` to handle HK/US:

```python
@router.get("/{code}/profile")
def get_stock_profile(code: str, session: Session = Depends(get_session)):
    stock = session.get(Stock, code)
    if not stock and code.isdigit():
        code = code.zfill(6)
        stock = session.get(Stock, code)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # For HK/US stocks, try to fetch from yfinance if no profile
    if stock.market not in ("SH", "SZ", "BJ") and not stock.profile_updated_at:
        from backend.collectors.hk_us.profile import fetch_hk_us_profile
        stock = fetch_hk_us_profile(session, stock.code) or stock

    try:
        concepts = json.loads(stock.concepts or "[]")
    except json.JSONDecodeError:
        concepts = []
    return {
        "code": stock.code,
        "name": stock.name,
        "business": stock.business,
        "industry": stock.industry,
        "concepts": concepts,
        "total_share": stock.total_share,
        "float_share": stock.float_share,
        "total_mv": stock.total_mv,
        "float_mv": stock.float_mv,
        "pe": stock.pe,
        "pb": stock.pb,
        "list_date": stock.list_date,
        "chairman": stock.chairman,
        "manager": stock.manager,
        "setup_date": stock.setup_date,
        "province": stock.province,
        "city": stock.city,
        "introduction": stock.introduction,
        "main_business": stock.main_business,
        "website": stock.website,
        "employees": stock.employees,
        "office": stock.office,
    }
```

- [ ] **Step 3: Update `routers/scores.py` — leaderboard market filter and code format**

In `get_leaderboard`, add `market` query param and fix `code.zfill(6)`:

Add `market` parameter:
```python
@router.get("/leaderboard")
def get_leaderboard(
    type: str = Query("other"),
    strategy: str = Query("short_term"),
    market: str = Query(None),
    session: Session = Depends(get_session),
):
```

After filtering by watchlist, add market filter:
```python
    if type == "watchlist":
        all_codes = {c for c in all_codes if stocks[c].is_watchlist}

    if market:
        if market == "HK":
            all_codes = {c for c in all_codes if stocks[c].market == "HK"}
        elif market == "US":
            all_codes = {c for c in all_codes if stocks[c].market == "US"}
        elif market in ("SH", "SZ", "BJ"):
            all_codes = {c for c in all_codes if stocks[c].market in ("SH", "SZ", "BJ")}
```

In `get_stock_detail`, fix the `code.zfill(6)` to only apply for A-share codes:

```python
@router.get("/{code}")
def get_stock_detail(code: str, session: Session = Depends(get_session)):
    latest = _latest_date(session)
    stock = session.get(Stock, code)
    if not stock and code.isdigit():
        code = code.zfill(6)
        stock = session.get(Stock, code)
    if not stock:
        return {"error": "暂无评分数据"}
```

Similarly fix `get_score_history`:
```python
@router.get("/{code}/history")
def get_score_history(
    code: str, strategy: str = Query("trend"),
    days: int = Query(30, ge=7, le=365),
    session: Session = Depends(get_session),
):
    stock = session.get(Stock, code)
    if not stock and code.isdigit():
        code = code.zfill(6)
```

- [ ] **Step 4: Verify all routers load**

Run: `uv run python -c "from backend.main import app; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/services.py backend/routers/stocks.py backend/routers/scores.py
git commit -m "feat: market-aware services, API routes, and leaderboard filtering"
```

---

### Task 9: Frontend — Dashboard HK/US support

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`
- Modify: `frontend/src/api/index.js`

- [ ] **Step 1: Update `api/index.js` — add market param to leaderboard**

Change the `getLeaderboard` function:

```javascript
export const getLeaderboard = (type, strategy, market) =>
  api.get('/scores/leaderboard', { params: { type, strategy, market: market || undefined } }).then(r => r.data)
```

- [ ] **Step 2: Update `Dashboard.vue` — replace HK placeholder with real data**

Replace the full `<script setup>` section:

```javascript
import { ref, shallowRef, watch, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import ScoreTable from '../components/ScoreTable.vue'
import { getLeaderboard } from '../api'

const route = useRoute()
const strategy = ref('short_term')
const rows = shallowRef([])
const loading = ref(false)
const showGuide = ref(false)

const isHKUS = computed(() => route.path === '/hk')

const hkUsTabs = [
  { value: 'hsi', label: '恒生指数', market: 'HK', tag: 'hsi' },
  { value: 'hstech', label: '恒生科技', market: 'HK', tag: 'hstech' },
  { value: 'sp500', label: 'S&P 500', market: 'US', tag: 'sp500' },
  { value: 'nasdaq100', label: '纳斯达克100', market: 'US', tag: 'nasdaq100' },
]
const hkUsTab = ref('hsi')

const strategyTabs = computed(() => {
  if (isHKUS.value) {
    return [
      { value: 'short_term', label: '短线策略' },
      { value: 'trend', label: '趋势策略' },
    ]
  }
  return [
    { value: 'short_term', label: '短线策略' },
    { value: 'trend', label: '趋势策略' },
    { value: 'setup', label: '埋伏策略' },
  ]
})

const currentStrategyLabel = computed(() =>
  strategyTabs.value.find(s => s.value === strategy.value)?.label || ''
)

const strategyDescriptions = {
  short_term: {
    technical: { key: 'technical', label: '技术面', color: '#60a5fa', desc: '价格动量 · 量能配合 · 趋势结构 · 趋势健康' },
    fundamental: { key: 'fundamental', label: '基本面', color: '#34d399', desc: 'PE · PB · ROE · 净利润增速' },
    heat: { key: 'heat', label: '市场热度', color: '#fb923c', desc: '涨跌幅 · 换手率 · 量比' },
  },
  trend: {
    technical: { key: 'technical', label: '技术面 55%', color: '#60a5fa', desc: '13日爆发力18分 · 攻击放量20分 · 均线排列10分 · 双通道健康10分' },
    fundamental: { key: 'fundamental', label: '基本面', color: '#34d399', desc: 'PE · PB · ROE · 净利润增速' },
    heat: { key: 'heat', label: '市场热度', color: '#fb923c', desc: '涨跌幅 · 换手率 · 量比' },
  },
  setup: {
    setup: { key: 'setup', label: '蓄势信号 55%', color: '#a78bfa', desc: '底部缩量11 · 温和放量8 · 均线收敛8 · 金叉信号11 · 跌幅充分6 · MA5斜率+站上8 · RSI低位3' },
    capital: { key: 'capital', label: '资金面(温和) 30%', color: '#f59e0b', desc: '温和净流入15 · 持续流入10 · 超大单不流出5' },
    heat: { key: 'heat', label: '热度面(低热度) 15%', color: '#fb923c', desc: '低换手8 · 低振幅4 · 量比适中3' },
  },
}

const strategyDimensions = {
  short_term: Object.values(strategyDescriptions.short_term),
  trend: Object.values(strategyDescriptions.trend),
  setup: Object.values(strategyDescriptions.setup),
}
const currentDimensions = computed(() => strategyDimensions[strategy.value] || [])

function getMarketFilter() {
  if (!isHKUS.value) return undefined
  const tab = hkUsTabs.find(t => t.value === hkUsTab.value)
  return tab?.market
}

async function load() {
  loading.value = true
  try {
    const res = await getLeaderboard(
      isHKUS.value ? 'other' : (route.path === '/watchlist' ? 'watchlist' : 'other'),
      strategy.value,
      getMarketFilter()
    )
    rows.value = res.stocks || []
  } catch { rows.value = [] }
  loading.value = false
}

watch(strategy, load)
watch(hkUsTab, load)
watch(() => route.path, load)
onMounted(load)
```

Replace the full `<template>` section:

```html
<template>
  <!-- 港美股 -->
  <div v-if="isHKUS" class="p-6">
    <div class="flex items-center justify-between mb-4">
      <div class="flex gap-5 border-b border-gray-800">
        <button v-for="t in hkUsTabs" :key="t.value"
          @click="hkUsTab = t.value"
          class="pb-2 text-sm font-medium border-b-2 transition-colors"
          :class="hkUsTab === t.value ? 'border-amber-400 text-amber-400' : 'border-transparent text-gray-500 hover:text-gray-300'">
          {{ t.label }}
        </button>
      </div>
      <div class="flex gap-3 border-b border-gray-800">
        <button v-for="s in strategyTabs" :key="s.value"
          @click="strategy = s.value"
          class="pb-2 text-sm font-medium border-b-2 transition-colors"
          :class="strategy === s.value ? 'border-amber-400 text-amber-400' : 'border-transparent text-gray-500 hover:text-gray-300'">
          {{ s.label }}
        </button>
      </div>
    </div>
    <ScoreTable :rows="rows" :strategy="strategy" />
    <div v-if="!rows.length && !loading" class="text-center py-12 text-gray-600">暂无数据，请先触发同步</div>
  </div>

  <!-- A股 / 自选 -->
  <div v-else class="p-6">
    <div class="flex items-center justify-between mb-4">
      <div class="flex gap-5 border-b border-gray-800">
        <button v-for="s in strategyTabs" :key="s.value"
          @click="strategy = s.value"
          class="pb-2 text-sm font-medium border-b-2 transition-colors"
          :class="strategy === s.value ? 'border-amber-400 text-amber-400' : 'border-transparent text-gray-500 hover:text-gray-300'">
          {{ s.label }}
        </button>
      </div>
      <button @click="showGuide = !showGuide"
        class="bg-gray-800 border rounded-md px-2.5 py-1 text-xs transition-colors"
        :class="showGuide ? 'border-blue-500 text-blue-400' : 'border-gray-700 text-gray-400 hover:text-gray-200'">
        ? 评分说明
      </button>
    </div>

    <div v-if="showGuide" class="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-4">
      <h3 class="text-amber-400 text-sm font-bold mb-3">{{ currentStrategyLabel }}权重</h3>
      <div class="grid grid-cols-3 gap-4">
        <div v-for="d in currentDimensions" :key="d.key" class="bg-gray-950 rounded-lg p-3" :style="{ borderTop: `2px solid ${d.color}` }">
          <div class="font-bold text-xs" :style="{ color: d.color }">{{ d.label }}</div>
          <div class="text-gray-500 text-xs mt-1.5 leading-relaxed">{{ d.desc }}</div>
        </div>
      </div>
    </div>

    <ScoreTable :rows="rows" :strategy="strategy" @added="load" />
    <div v-if="!rows.length && !loading" class="text-center py-12 text-gray-600">暂无数据，请先触发同步</div>
  </div>
</template>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/Dashboard.vue frontend/src/api/index.js
git commit -m "feat: HK/US dashboard with index tabs and market filtering"
```

---

### Task 10: Frontend — StockDetail multi-market + router

**Files:**
- Modify: `frontend/src/views/StockDetail.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Update `StockDetail.vue` — market-aware external links**

Find the external link line:

```html
<a :href="`https://stockpage.10jqka.com.cn/${data.code}/`" target="_blank" class="text-xs text-blue-400 hover:text-blue-300">同花顺 ↗</a>
```

Replace with market-aware links:

```html
<a v-if="stockMarket === 'US'" :href="`https://finance.yahoo.com/quote/${data.code}`" target="_blank" class="text-xs text-blue-400 hover:text-blue-300">Yahoo Finance ↗</a>
<a v-else-if="stockMarket === 'HK'" :href="`https://finance.yahoo.com/quote/${String(parseInt(data.code)).padStart(4, '0')}.HK`" target="_blank" class="text-xs text-blue-400 hover:text-blue-300">Yahoo Finance ↗</a>
<a v-else :href="`https://stockpage.10jqka.com.cn/${data.code}/`" target="_blank" class="text-xs text-blue-400 hover:text-blue-300">同花顺 ↗</a>
```

Add `stockMarket` computed property in the `<script setup>`:

```javascript
const stockMarket = computed(() => {
  if (!data.value) return 'SH'
  const code = data.value.code || ''
  // Check profile or raw data for market info
  return data.value.raw?.market || 'SH'
})
```

Update the `load()` function to get market info from the profile API response:

```javascript
async function load() {
  const code = route.params.code
  const [detail, prof, watched] = await Promise.allSettled([
    getStockDetail(code),
    getStockProfile(code),
    checkWatchlist(code),
  ])
  if (detail.status === 'fulfilled') data.value = detail.value
  if (prof.status === 'fulfilled') {
    profile.value = prof.value
    // Store market from profile
    if (prof.value?.market) data.value = { ...data.value, _market: prof.value.market }
  }
  if (watched.status === 'fulfilled') isWatchlist.value = watched.value
  aiResult.value = ''
  aiError.value = ''
  // ... rest unchanged
```

Update `stockMarket` to use the stored market:

```javascript
const stockMarket = computed(() => {
  if (!data.value) return 'SH'
  return data.value._market || 'SH'
})
```

Also update the `get_stock_profile` endpoint in `backend/routers/stocks.py` to return market:

In the profile response dict, add:
```python
    "market": stock.market,
```

- [ ] **Step 2: Update `router/index.js` — no changes needed, already routes `/hk` to Dashboard**

The existing routes work as-is:
```javascript
{ path: '/hk', component: Dashboard },
```

No change needed.

- [ ] **Step 3: Update `App.vue` — fix search for multi-market**

In `App.vue`, the `goDetail` function already works with any code. The search API now returns multi-market results. The existing code navigates to `/stock/{code}` which works for all markets.

No changes needed to `App.vue`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/StockDetail.vue backend/routers/stocks.py
git commit -m "feat: market-aware stock detail with Yahoo Finance links for HK/US"
```

---

## Self-Review

### Spec Coverage
- [x] Universe sync for 4 indices → Task 2, Task 7
- [x] Technical collector → Task 3
- [x] Fundamental collector → Task 4
- [x] Market heat collector → Task 5
- [x] News collector (degraded) → Task 5
- [x] Capital dimension (skipped for HK/US) → Task 6
- [x] Engine market-aware scoring → Task 6
- [x] Pipeline integration → Task 7
- [x] Services market-aware → Task 8
- [x] Frontend Dashboard → Task 9
- [x] Frontend StockDetail → Task 10
- [x] Profile for HK/US → Task 5, Task 10
- [x] Strategy weight redistribution → Task 6

### Placeholder Scan
- No TBD, TODO, or "implement later" found
- All code blocks contain complete implementations
- No "add appropriate error handling" patterns

### Type Consistency
- `target_codes: dict[str, str]` (code→market) used consistently across all HK/US collectors
- `_yf_code()` function signature identical across all HK/US files
- `market` field values consistent: SH/SZ/BJ/HK/US
- Score/Strategy model fields unchanged
