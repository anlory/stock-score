# Tushare 数据源迁移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将除 `news.py` 外的所有 collector 从 pywencai/腾讯K线/akshare/东方财富迁移至 tushare，使用 `jiaoch.site` 代理。

**Architecture:** 新建 `collectors/tushare_client.py` 作为单例 pro 实例和格式转换工具，各 collector 独立迁移。按批量日线 → universe → profile → trend 顺序，最后清理旧文件。

**Tech Stack:** tushare, pandas, pandas_ta, SQLAlchemy, pytest + unittest.mock

---

## File Map

| 操作 | 文件 |
|------|------|
| 新建 | `backend/collectors/tushare_client.py` |
| 修改 | `backend/config.py` |
| 替换 | `backend/collectors/technical.py` |
| 替换 | `backend/collectors/fundamental.py` |
| 替换 | `backend/collectors/market_heat.py` |
| 替换 | `backend/collectors/capital.py` |
| 替换 | `backend/collectors/universe.py` |
| 替换 | `backend/collectors/profile.py` |
| 替换 | `backend/collectors/trend.py` |
| 删除 | `backend/collectors/tencent_kline.py` |
| 修改 | `pyproject.toml` |
| 新建/修改 | `tests/test_tushare_client.py` |
| 修改 | `tests/test_profile_collector.py` |
| 修改 | `tests/test_trend_collector.py` |

---

## Task 1: 共享基础设施 — tushare_client.py + config.py

**Files:**
- Create: `backend/collectors/tushare_client.py`
- Modify: `backend/config.py`
- Create: `tests/test_tushare_client.py`

- [ ] **Step 1: Write failing tests for format conversion**

```python
# tests/test_tushare_client.py
from backend.collectors.tushare_client import to_ts_code, from_ts_code, to_ts_date

def test_to_ts_code_sh():
    assert to_ts_code("600519") == "600519.SH"

def test_to_ts_code_sz():
    assert to_ts_code("000001") == "000001.SZ"

def test_to_ts_code_bj():
    assert to_ts_code("430047") == "430047.BJ"

def test_from_ts_code():
    assert from_ts_code("000001.SZ") == "000001"
    assert from_ts_code("600519.SH") == "600519"

def test_to_ts_date():
    assert to_ts_date("2024-01-01") == "20240101"
    assert to_ts_date("2026-04-25") == "20260425"
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd /Users/anlory/Project/stock_score
pytest tests/test_tushare_client.py -v
```

Expected: `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Add tushare to dependencies**

In `pyproject.toml`, add `"tushare>=1.2.89"` to `dependencies`:

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
]
```

（同时移除 `akshare` 和 `efinance`，保留 `pywencai` 供 news.py 使用）

```bash
uv sync
```

- [ ] **Step 4: Add TUSHARE_TOKEN and TUSHARE_URL to config.py**

`backend/config.py` 在文件顶部加 `import os`（若无），在末尾追加：

```python
# Tushare
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
TUSHARE_URL = os.getenv("TUSHARE_URL", "http://jiaoch.site")
```

- [ ] **Step 5: Create tushare_client.py**

```python
# backend/collectors/tushare_client.py
import tushare as ts
from backend.config import TUSHARE_TOKEN, TUSHARE_URL

_pro = None

# Populated by universe.py during sync; used by trend.py
# Maps industry name (str) → THS index ts_code (str), e.g. "银行" → "885096.TI"
INDUSTRY_TS_CODE_MAP: dict[str, str] = {}


def get_pro():
    global _pro
    if _pro is None:
        _pro = ts.pro_api(TUSHARE_TOKEN)
        _pro._DataApi__token = TUSHARE_TOKEN
        _pro._DataApi__http_url = TUSHARE_URL
    return _pro


def to_ts_code(code: str) -> str:
    """'000001' → '000001.SZ'"""
    if code.startswith(("6", "5", "9")):
        return f"{code}.SH"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return f"{code}.SZ"


def from_ts_code(ts_code: str) -> str:
    """'000001.SZ' → '000001'"""
    return ts_code.split(".")[0]


def to_ts_date(iso_date: str) -> str:
    """'2024-01-01' → '20240101'"""
    return iso_date.replace("-", "")
```

- [ ] **Step 6: Run tests — confirm they pass**

```bash
pytest tests/test_tushare_client.py -v
```

Expected: 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/collectors/tushare_client.py backend/config.py pyproject.toml tests/test_tushare_client.py
git commit -m "feat: add tushare client singleton and format conversion utils"
```

---

## Task 2: 迁移 technical.py

**Files:**
- Modify: `backend/collectors/technical.py`
- Create: `tests/test_technical_collector.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_technical_collector.py
import pandas as pd
from unittest.mock import patch, MagicMock
from backend.collectors.technical import collect_technical
from backend.models import DailyData

def _make_daily_df(code="000001.SZ", n=90):
    """Return a tushare-format daily DataFrame."""
    import numpy as np
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    closes = 10.0 + np.cumsum(np.random.randn(n) * 0.1)
    df = pd.DataFrame({
        "ts_code": code,
        "trade_date": [d.strftime("%Y%m%d") for d in dates],
        "open": closes * 0.99,
        "high": closes * 1.01,
        "low": closes * 0.98,
        "close": closes,
        "pre_close": closes * 0.99,
        "change": closes * 0.01,
        "pct_chg": 1.0,
        "vol": 1e6,
        "amount": 1e7,
    })
    return df.sort_values("trade_date")


@patch("backend.collectors.technical.get_pro")
def test_collect_technical_writes_indicators(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro
    mock_pro.daily.return_value = _make_daily_df("000001.SZ")

    count = collect_technical(db_session, {"000001"})

    assert count == 1
    row = db_session.query(DailyData).filter_by(code="000001").first()
    assert row is not None
    assert row.close is not None
    assert row.ma5 is not None
    assert row.macd_dif is not None
    assert row.rsi14 is not None


@patch("backend.collectors.technical.get_pro")
def test_collect_technical_skips_insufficient_data(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro
    # Only 10 rows — not enough for indicators
    mock_pro.daily.return_value = _make_daily_df("000001.SZ", n=10)

    count = collect_technical(db_session, {"000001"})
    assert count == 0
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_technical_collector.py -v
```

Expected: FAIL (get_pro not imported in technical.py yet)

- [ ] **Step 3: Replace technical.py**

```python
# backend/collectors/technical.py
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

import pandas as pd
import pandas_ta as ta

from backend.collectors.tushare_client import get_pro, to_ts_code, to_ts_date
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)
_MAX_WORKERS = 10


def _process_one(code: str, today: str) -> dict | None:
    try:
        pro = get_pro()
        start = to_ts_date((date.fromisoformat(today) - timedelta(days=130)).isoformat())
        df = pro.daily(ts_code=to_ts_code(code), start_date=start, end_date=to_ts_date(today))
        if df is None or len(df) < 15:
            return None

        df = df.sort_values("trade_date").reset_index(drop=True)
        df = df.rename(columns={"vol": "volume"})

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

        return {
            "code": code,
            "date": today,
            "close": _f(last, "close"),
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
        }
    except Exception as e:
        logger.error(f"Technical failed for {code}: {e}")
        return None


def collect_technical(session, target_codes: set[str] = None) -> int:
    today = date.today().isoformat()
    codes = sorted(target_codes) if target_codes else []
    if not codes:
        logger.warning("No target codes for technical collection")
        return 0

    results = []
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_process_one, code, today): code for code in codes}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    count = 0
    for record in results:
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"Technical upsert failed for {record.get('code')}: {e}")

    session.commit()
    logger.info(f"Technical data collected: {count} stocks")
    return count


def _f(row, col):
    val = row.get(col)
    try:
        return round(float(val), 4) if pd.notna(val) else None
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 4: Run — confirm pass**

```bash
pytest tests/test_technical_collector.py -v
```

Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/collectors/technical.py tests/test_technical_collector.py
git commit -m "feat: migrate technical collector to tushare daily()"
```

---

## Task 3: 迁移 fundamental.py

**Files:**
- Modify: `backend/collectors/fundamental.py`
- Create: `tests/test_fundamental_collector.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_fundamental_collector.py
import pandas as pd
from unittest.mock import patch, MagicMock
from backend.collectors.fundamental import collect_fundamental, _latest_fina_period
from backend.models import DailyData


def test_latest_fina_period_early_year():
    # Month <= 4: use prior year Q3
    result = _latest_fina_period(2026, 3)
    assert result == "20250930"


def test_latest_fina_period_mid_year():
    # Month 5-8: use prior year annual
    result = _latest_fina_period(2026, 6)
    assert result == "20251231"


def test_latest_fina_period_q3():
    # Month 9-10: use current year semi-annual
    result = _latest_fina_period(2026, 9)
    assert result == "20260630"


def test_latest_fina_period_q4():
    # Month 11+: use current year Q3
    result = _latest_fina_period(2026, 11)
    assert result == "20260930"


@patch("backend.collectors.fundamental.get_pro")
def test_collect_fundamental_writes_pe_pb_roe(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro

    mock_pro.daily_basic.return_value = pd.DataFrame([{
        "ts_code": "000001.SZ", "trade_date": "20260425",
        "pe_ttm": 8.5, "pb": 0.9, "total_mv": 2000000.0,  # 万元
    }])
    mock_pro.fina_indicator.return_value = pd.DataFrame([{
        "ts_code": "000001.SZ", "end_date": "20250930",
        "roe": 12.3, "netprofit_yoy": 8.5,
    }])

    count = collect_fundamental(db_session, {"000001"})

    assert count == 1
    row = db_session.query(DailyData).filter_by(code="000001").first()
    assert row.pe == 8.5
    assert row.pb == 0.9
    assert abs(row.market_cap - 200.0) < 0.01  # 2000000万 / 10000 = 200亿
    assert row.roe == 12.3
    assert row.profit_growth_yoy == 8.5
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_fundamental_collector.py -v
```

Expected: FAIL

- [ ] **Step 3: Replace fundamental.py**

```python
# backend/collectors/fundamental.py
import logging
from datetime import date
from backend.collectors.tushare_client import get_pro, to_ts_code, to_ts_date
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)


def _latest_fina_period(year: int, month: int) -> str:
    if month <= 4:
        return f"{year - 1}0930"
    if month <= 8:
        return f"{year - 1}1231"
    if month <= 10:
        return f"{year}0630"
    return f"{year}0930"


def collect_fundamental(session, target_codes: set[str] = None) -> int:
    today = date.today()
    today_str = today.isoformat()
    today_ts = to_ts_date(today_str)
    period = _latest_fina_period(today.year, today.month)

    if not target_codes:
        return 0

    pro = get_pro()

    # --- PE / PB / market_cap from daily_basic (full market, one call) ---
    basic_df = pro.daily_basic(trade_date=today_ts, fields="ts_code,pe_ttm,pb,total_mv")
    basic_map: dict[str, dict] = {}
    if basic_df is not None and not basic_df.empty:
        for _, row in basic_df.iterrows():
            code = row["ts_code"].split(".")[0]
            if code in target_codes:
                basic_map[code] = {
                    "pe": _safe_float(row.get("pe_ttm")),
                    "pb": _safe_float(row.get("pb")),
                    "market_cap": round(_safe_float(row.get("total_mv"), 0) / 10000, 4),  # 万→亿
                }

    # --- ROE / profit_growth_yoy from fina_indicator (per stock, tushare only accepts single ts_code) ---
    fina_map: dict[str, dict] = {}
    for code in sorted(target_codes):
        try:
            df = pro.fina_indicator(ts_code=to_ts_code(code), period=period, fields="ts_code,roe,netprofit_yoy")
            if df is None or df.empty:
                continue
            row = df.iloc[0]
            fina_map[code] = {
                "roe": _safe_float(row.get("roe")),
                "profit_growth_yoy": _safe_float(row.get("netprofit_yoy")),
            }
        except Exception as e:
            logger.error(f"fina_indicator failed for {code}: {e}")

    count = 0
    for code in target_codes:
        record: dict = {"code": code, "date": today_str}
        record.update(basic_map.get(code, {}))
        record.update(fina_map.get(code, {}))
        if len(record) <= 2:
            continue
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"Fundamental upsert failed for {code}: {e}")

    session.commit()
    logger.info(f"Fundamental data collected: {count} stocks")
    return count


def _safe_float(val, default=None):
    try:
        import math
        v = float(val)
        return None if math.isnan(v) else round(v, 4)
    except (TypeError, ValueError):
        return default
```

- [ ] **Step 4: Run — confirm pass**

```bash
pytest tests/test_fundamental_collector.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/collectors/fundamental.py tests/test_fundamental_collector.py
git commit -m "feat: migrate fundamental collector to tushare daily_basic + fina_indicator"
```

---

## Task 4: 迁移 market_heat.py

**Files:**
- Modify: `backend/collectors/market_heat.py`
- Create: `tests/test_market_heat_collector.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_market_heat_collector.py
import pandas as pd
from unittest.mock import patch, MagicMock, call
from backend.collectors.market_heat import collect_market_heat
from backend.models import DailyData


@patch("backend.collectors.market_heat.get_pro")
def test_collect_market_heat_writes_fields(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro

    mock_pro.daily.return_value = pd.DataFrame([{
        "ts_code": "000001.SZ", "trade_date": "20260425", "pct_chg": 2.5, "vol": 1e6,
    }])
    mock_pro.daily_basic.return_value = pd.DataFrame([{
        "ts_code": "000001.SZ", "trade_date": "20260425",
        "turnover_rate": 3.2, "volume_ratio": 1.8,
    }])
    # No limit-up stocks today
    mock_pro.limit_list_d.return_value = pd.DataFrame(columns=["ts_code", "trade_date"])

    count = collect_market_heat(db_session, {"000001"})

    assert count == 1
    row = db_session.query(DailyData).filter_by(code="000001").first()
    assert row.change_pct == 2.5
    assert row.turnover_rate == 3.2
    assert row.volume_ratio == 1.8
    assert row.consecutive_limit_up == 0


@patch("backend.collectors.market_heat.get_pro")
def test_consecutive_limit_up_counted(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro

    mock_pro.daily.return_value = pd.DataFrame([{
        "ts_code": "000001.SZ", "trade_date": "20260425", "pct_chg": 9.9, "vol": 2e6,
    }])
    mock_pro.daily_basic.return_value = pd.DataFrame([{
        "ts_code": "000001.SZ", "trade_date": "20260425",
        "turnover_rate": 5.0, "volume_ratio": 3.0,
    }])

    # Stock hit limit-up for 2 consecutive days
    def limit_side_effect(trade_date, **kw):
        return pd.DataFrame([{"ts_code": "000001.SZ", "trade_date": trade_date}])

    mock_pro.limit_list_d.side_effect = limit_side_effect
    # trade_cal returns 10 trading days
    mock_pro.trade_cal.return_value = pd.DataFrame({
        "cal_date": [f"2026042{i}" for i in range(6, 10)] + ["20260420", "20260421",
                     "20260422", "20260423", "20260424", "20260425"],
        "is_open": ["1"] * 10,
    })

    count = collect_market_heat(db_session, {"000001"})
    assert count == 1
    row = db_session.query(DailyData).filter_by(code="000001").first()
    assert row.consecutive_limit_up >= 1
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_market_heat_collector.py -v
```

Expected: FAIL

- [ ] **Step 3: Replace market_heat.py**

```python
# backend/collectors/market_heat.py
import logging
from datetime import date, timedelta
from backend.collectors.tushare_client import get_pro, to_ts_date
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)


def _get_recent_trade_dates(pro, today_ts: str, n: int = 10) -> list[str]:
    start_ts = to_ts_date((date.fromisoformat(today_ts[:4] + "-" + today_ts[4:6] + "-" + today_ts[6:]) - timedelta(days=20)).isoformat())
    cal = pro.trade_cal(start_date=start_ts, end_date=today_ts, is_open="1")
    if cal is None or cal.empty:
        return [today_ts]
    dates = sorted(cal["cal_date"].tolist())
    return dates[-n:]


def collect_market_heat(session, target_codes: set[str] = None) -> int:
    today = date.today()
    today_str = today.isoformat()
    today_ts = to_ts_date(today_str)

    if not target_codes:
        return 0

    pro = get_pro()

    # --- change_pct from daily ---
    daily_df = pro.daily(trade_date=today_ts, fields="ts_code,pct_chg,vol")
    daily_map: dict[str, float] = {}
    if daily_df is not None and not daily_df.empty:
        for _, row in daily_df.iterrows():
            code = row["ts_code"].split(".")[0]
            if code in target_codes:
                daily_map[code] = _sf(row.get("pct_chg"))

    # --- turnover_rate, volume_ratio from daily_basic ---
    basic_df = pro.daily_basic(trade_date=today_ts, fields="ts_code,turnover_rate,volume_ratio")
    basic_map: dict[str, dict] = {}
    if basic_df is not None and not basic_df.empty:
        for _, row in basic_df.iterrows():
            code = row["ts_code"].split(".")[0]
            if code in target_codes:
                basic_map[code] = {
                    "turnover_rate": _sf(row.get("turnover_rate")),
                    "volume_ratio": _sf(row.get("volume_ratio")),
                }

    # --- consecutive_limit_up: query last 10 trading days ---
    trade_dates = _get_recent_trade_dates(pro, today_ts, n=10)
    # limit_days[code] = list of dates (desc) where stock hit limit-up
    limit_sets: list[set[str]] = []
    for td in reversed(trade_dates):  # newest first
        try:
            df = pro.limit_list_d(trade_date=td, fields="ts_code,trade_date")
            if df is not None and not df.empty:
                limit_sets.append(set(r.split(".")[0] for r in df["ts_code"].tolist()))
            else:
                limit_sets.append(set())
        except Exception as e:
            logger.warning(f"limit_list_d failed for {td}: {e}")
            limit_sets.append(set())

    def _consecutive(code: str) -> int:
        count = 0
        for s in limit_sets:
            if code in s:
                count += 1
            else:
                break
        return count

    count = 0
    for code in target_codes:
        record: dict = {"code": code, "date": today_str}
        if code in daily_map:
            record["change_pct"] = daily_map[code]
        record.update(basic_map.get(code, {}))
        record["consecutive_limit_up"] = _consecutive(code)
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"Heat upsert failed for {code}: {e}")

    session.commit()
    logger.info(f"Market heat data collected: {count} stocks")
    return count


def _sf(val, default=None):
    try:
        import math
        v = float(val)
        return None if math.isnan(v) else round(v, 4)
    except (TypeError, ValueError):
        return default
```

- [ ] **Step 4: Run — confirm pass**

```bash
pytest tests/test_market_heat_collector.py -v
```

Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/collectors/market_heat.py tests/test_market_heat_collector.py
git commit -m "feat: migrate market_heat collector to tushare daily + daily_basic + limit_list_d"
```

---

## Task 5: 迁移 capital.py

**Files:**
- Modify: `backend/collectors/capital.py`
- Create: `tests/test_capital_collector.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_capital_collector.py
import pandas as pd
from unittest.mock import patch, MagicMock
from backend.collectors.capital import collect_capital
from backend.models import DailyData


@patch("backend.collectors.capital.get_pro")
def test_collect_capital_writes_inflow(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro

    # Today's full-market moneyflow
    mock_pro.moneyflow.side_effect = [
        pd.DataFrame([{
            "ts_code": "000001.SZ",
            "trade_date": "20260425",
            "buy_lg_amount": 500.0,
            "buy_elg_amount": 300.0,
            "net_mf_amount": 200.0,
        }]),
        # 5-day per-stock call
        pd.DataFrame([
            {"ts_code": "000001.SZ", "trade_date": "20260421", "net_mf_amount": 100.0},
            {"ts_code": "000001.SZ", "trade_date": "20260422", "net_mf_amount": 150.0},
            {"ts_code": "000001.SZ", "trade_date": "20260423", "net_mf_amount": -50.0},
            {"ts_code": "000001.SZ", "trade_date": "20260424", "net_mf_amount": 80.0},
            {"ts_code": "000001.SZ", "trade_date": "20260425", "net_mf_amount": 200.0},
        ]),
    ]

    count = collect_capital(db_session, {"000001"})

    assert count == 1
    row = db_session.query(DailyData).filter_by(code="000001").first()
    assert row.main_inflow_today == 800.0   # 500 + 300
    assert row.super_large_inflow == 300.0
    assert abs(row.main_inflow_5d - 480.0) < 0.01  # 100+150-50+80+200
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_capital_collector.py -v
```

Expected: FAIL

- [ ] **Step 3: Replace capital.py**

```python
# backend/collectors/capital.py
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from backend.collectors.tushare_client import get_pro, to_ts_code, to_ts_date
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)
_MAX_WORKERS = 10


def _fetch_5d_sum(pro, code: str, today_ts: str) -> float | None:
    start_ts = to_ts_date((date.fromisoformat(
        today_ts[:4] + "-" + today_ts[4:6] + "-" + today_ts[6:]
    ) - timedelta(days=14)).isoformat())
    try:
        df = pro.moneyflow(ts_code=to_ts_code(code), start_date=start_ts, end_date=today_ts,
                           fields="ts_code,trade_date,net_mf_amount")
        if df is None or df.empty:
            return None
        df = df.sort_values("trade_date")
        last5 = df.tail(5)["net_mf_amount"]
        return round(float(last5.sum()), 2)
    except Exception as e:
        logger.error(f"Capital 5d failed for {code}: {e}")
        return None


def collect_capital(session, target_codes: set[str] = None) -> int:
    today = date.today().isoformat()
    today_ts = to_ts_date(today)

    if not target_codes:
        return 0

    pro = get_pro()

    # Today's full-market moneyflow
    today_df = pro.moneyflow(
        trade_date=today_ts,
        fields="ts_code,buy_lg_amount,buy_elg_amount,net_mf_amount"
    )
    today_map: dict[str, dict] = {}
    if today_df is not None and not today_df.empty:
        for _, row in today_df.iterrows():
            code = row["ts_code"].split(".")[0]
            if code in target_codes:
                lg = _sf(row.get("buy_lg_amount"), 0.0)
                elg = _sf(row.get("buy_elg_amount"), 0.0)
                today_map[code] = {
                    "main_inflow_today": round(lg + elg, 2),
                    "super_large_inflow": elg,
                }

    # 5-day cumulative per stock (concurrent)
    codes = sorted(target_codes)
    five_d_map: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_5d_sum, pro, code, today_ts): code for code in codes}
        for future in as_completed(futures):
            code = futures[future]
            val = future.result()
            if val is not None:
                five_d_map[code] = val

    count = 0
    for code in target_codes:
        record: dict = {"code": code, "date": today}
        record.update(today_map.get(code, {}))
        if code in five_d_map:
            record["main_inflow_5d"] = five_d_map[code]
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"Capital upsert failed for {code}: {e}")

    session.commit()
    logger.info(f"Capital data collected: {count} stocks")
    return count


def _sf(val, default=None):
    try:
        import math
        v = float(val)
        return default if math.isnan(v) else round(v, 2)
    except (TypeError, ValueError):
        return default
```

- [ ] **Step 4: Run — confirm pass**

```bash
pytest tests/test_capital_collector.py -v
```

Expected: 1 test PASS

- [ ] **Step 5: Commit**

```bash
git add backend/collectors/capital.py tests/test_capital_collector.py
git commit -m "feat: migrate capital collector to tushare moneyflow()"
```

---

## Task 6: 迁移 universe.py

**Files:**
- Modify: `backend/collectors/universe.py`
- Create: `tests/test_universe_collector.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_universe_collector.py
import pandas as pd
from unittest.mock import patch, MagicMock
from backend.collectors.universe import sync_universe
from backend.models import Stock


@patch("backend.collectors.universe.get_pro")
def test_sync_universe_inserts_index_stocks(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro

    # index_member returns hs300 stock
    mock_pro.index_member.return_value = pd.DataFrame([{
        "index_code": "000300.SH", "con_code": "600519.SH", "con_name": "贵州茅台",
    }])
    # stock_basic returns name + industry
    mock_pro.stock_basic.return_value = pd.DataFrame([{
        "ts_code": "600519.SH", "name": "贵州茅台", "industry": "白酒", "market": "主板",
    }])
    # ths_index returns one industry index
    mock_pro.ths_index.return_value = pd.DataFrame([{
        "ts_code": "885096.TI", "name": "白酒", "type": "N",
    }])
    # ths_daily returns no hot sectors
    mock_pro.ths_daily.return_value = pd.DataFrame(columns=["ts_code", "pct_change"])

    total = sync_universe(db_session)

    assert total >= 1
    stock = db_session.query(Stock).filter_by(code="600519").first()
    assert stock is not None
    assert stock.name == "贵州茅台"
    assert stock.industry == "白酒"


@patch("backend.collectors.universe.get_pro")
def test_sync_universe_populates_industry_map(mock_get_pro, db_session):
    from backend.collectors import tushare_client
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro

    mock_pro.index_member.return_value = pd.DataFrame(columns=["con_code", "con_name"])
    mock_pro.stock_basic.return_value = pd.DataFrame(columns=["ts_code", "name", "industry", "market"])
    mock_pro.ths_index.return_value = pd.DataFrame([{
        "ts_code": "885096.TI", "name": "银行", "type": "N",
    }])
    mock_pro.ths_daily.return_value = pd.DataFrame(columns=["ts_code", "pct_change"])

    sync_universe(db_session)

    assert tushare_client.INDUSTRY_TS_CODE_MAP.get("银行") == "885096.TI"
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_universe_collector.py -v
```

Expected: FAIL

- [ ] **Step 3: Replace universe.py**

```python
# backend/collectors/universe.py
import json
import logging
import pandas as pd
from backend.collectors.tushare_client import get_pro, to_ts_date
from backend.collectors import tushare_client
from backend.database import upsert
from backend.models import Stock

logger = logging.getLogger(__name__)


def _get_market(code: str) -> str:
    if code.startswith(("6", "5", "9")):
        return "SH"
    if code.startswith(("4", "8")):
        return "BJ"
    return "SZ"


def _normalize(ts_code: str) -> str:
    return ts_code.split(".")[0]


def sync_universe(session, watchlist_codes: list[str] = None) -> int:
    pro = get_pro()
    from datetime import date
    today_ts = to_ts_date(date.today().isoformat())

    # 1. 全量股票基础信息（名称、行业）
    basic_df = pro.stock_basic(
        exchange="", list_status="L",
        fields="ts_code,name,industry,market"
    )
    basic_info: dict[str, dict] = {}
    if basic_df is not None and not basic_df.empty:
        for _, row in basic_df.iterrows():
            code = _normalize(row["ts_code"])
            basic_info[code] = {
                "name": str(row.get("name") or code),
                "industry": str(row.get("industry") or ""),
            }

    # 2. THS 行业指数列表 → 填充 INDUSTRY_TS_CODE_MAP
    ths_df = pro.ths_index(exchange="A", type="N")
    if ths_df is not None and not ths_df.empty:
        for _, row in ths_df.iterrows():
            name = str(row.get("name") or "")
            ts_code = str(row.get("ts_code") or "")
            if name and ts_code:
                tushare_client.INDUSTRY_TS_CODE_MAP[name] = ts_code

    # 3. 指数成分股
    index_map = {
        "000300.SH": "hs300",
        "000905.SH": "zz500",
        "399006.SZ": "cyb",
    }
    index_stocks: dict[str, dict] = {}
    for idx_code, tag in index_map.items():
        try:
            df = pro.index_member(index_code=idx_code, fields="con_code,con_name")
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                code = _normalize(str(row.get("con_code") or ""))
                if not code:
                    continue
                if code not in index_stocks:
                    info = basic_info.get(code, {})
                    index_stocks[code] = {
                        "name": str(row.get("con_name") or info.get("name") or code),
                        "industry": info.get("industry", ""),
                        "tags": [],
                    }
                index_stocks[code]["tags"].append(tag)
        except Exception as e:
            logger.error(f"index_member failed for {idx_code}: {e}")

    for code, info in index_stocks.items():
        market = _get_market(code)
        upsert(session, Stock, {
            "code": code, "name": info["name"], "market": market,
            "industry": info["industry"],
            "is_watchlist": False, "index_tags": json.dumps(info["tags"]),
        }, ["code"])

    # 4. 热门板块股票
    try:
        heat_df = pro.ths_daily(trade_date=today_ts)
        if heat_df is not None and not heat_df.empty and "pct_change" in heat_df.columns:
            top10 = heat_df.nlargest(10, "pct_change")["ts_code"].tolist()
            for ths_ts_code in top10:
                try:
                    member_df = pro.ths_member(ts_code=ths_ts_code)
                    if member_df is None or member_df.empty:
                        continue
                    top5 = member_df.head(5)
                    for _, row in top5.iterrows():
                        code = str(row.get("code") or "").zfill(6)
                        if not code or code == "000000":
                            continue
                        existing = session.get(Stock, code)
                        if not existing:
                            info = basic_info.get(code, {})
                            upsert(session, Stock, {
                                "code": code,
                                "name": info.get("name", code),
                                "market": _get_market(code),
                                "industry": info.get("industry", ""),
                                "is_watchlist": False,
                                "index_tags": "[]",
                            }, ["code"])
                except Exception as e:
                    logger.warning(f"ths_member failed for {ths_ts_code}: {e}")
    except Exception as e:
        logger.warning(f"ths_daily failed: {e}")

    # 5. 自选股
    if watchlist_codes:
        for raw_code in watchlist_codes:
            code = raw_code.zfill(6)
            market = _get_market(code)
            existing = session.get(Stock, code)
            if existing:
                existing.is_watchlist = True
            else:
                info = basic_info.get(code, {})
                upsert(session, Stock, {
                    "code": code,
                    "name": info.get("name", code),
                    "market": market,
                    "industry": info.get("industry", ""),
                    "is_watchlist": True,
                    "index_tags": "[]",
                }, ["code"])

    session.commit()
    total = session.query(Stock).count()
    logger.info(f"Universe synced: {total} stocks")
    return total
```

- [ ] **Step 4: Run — confirm pass**

```bash
pytest tests/test_universe_collector.py -v
```

Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/collectors/universe.py tests/test_universe_collector.py
git commit -m "feat: migrate universe sync to tushare index_member + ths_index/ths_daily"
```

---

## Task 7: 迁移 profile.py

**Files:**
- Modify: `backend/collectors/profile.py`
- Modify: `tests/test_profile_collector.py`

- [ ] **Step 1: Update test to match new internal function names**

现有测试 mock 了 `_fetch_individual_info`、`_fetch_business`、`_fetch_concepts`。新版保留相同函数名，但实现改为 tushare。测试本身只需更新 mock 内容和断言：

```python
# tests/test_profile_collector.py  — 完整替换
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import pandas as pd
from backend.models import Stock
from backend.collectors.profile import fetch_profile


def _seed_stock(session, code="000001", **kw):
    defaults = dict(code=code, name="平安银行", market="SZ", is_watchlist=False, index_tags="[]")
    defaults.update(kw)
    session.add(Stock(**defaults))
    session.commit()


@patch("backend.collectors.profile._fetch_concepts")
@patch("backend.collectors.profile._fetch_business")
@patch("backend.collectors.profile._fetch_individual_info")
def test_fetch_profile_populates_all_fields(mock_info, mock_business, mock_concepts, db_session):
    _seed_stock(db_session)
    mock_info.return_value = {
        "industry": "银行",
        "total_share": 194.06,
        "float_share": 194.05,
        "list_date": "1991-04-03",
    }
    mock_business.return_value = "主营业务：各项银行业务..."
    mock_concepts.return_value = ["金融改革", "大金融"]

    stock = fetch_profile(db_session, "000001")

    assert stock.industry == "银行"
    assert stock.total_share == 194.06
    assert stock.list_date == "1991-04-03"
    assert "银行业务" in stock.business
    assert json.loads(stock.concepts) == ["金融改革", "大金融"]
    assert stock.profile_updated_at is not None
    mock_info.assert_called_once()


@patch("backend.collectors.profile._fetch_individual_info")
def test_fetch_profile_cache_hit_skips_api(mock_info, db_session):
    _seed_stock(
        db_session,
        industry="银行",
        business="cached",
        profile_updated_at=datetime.now() - timedelta(days=5),
    )
    stock = fetch_profile(db_session, "000001")
    assert stock.business == "cached"
    mock_info.assert_not_called()


@patch("backend.collectors.profile._fetch_concepts")
@patch("backend.collectors.profile._fetch_business")
@patch("backend.collectors.profile._fetch_individual_info")
def test_fetch_profile_expired_cache_refetches(mock_info, mock_business, mock_concepts, db_session):
    _seed_stock(
        db_session, industry="银行", business="stale",
        profile_updated_at=datetime.now() - timedelta(days=40),
    )
    mock_info.return_value = {"industry": "银行", "total_share": 1.0, "float_share": 1.0, "list_date": "1991-04-03"}
    mock_business.return_value = "fresh"
    mock_concepts.return_value = []

    stock = fetch_profile(db_session, "000001")
    assert stock.business == "fresh"


@patch("backend.collectors.profile._fetch_individual_info", side_effect=RuntimeError("boom"))
def test_fetch_profile_on_error_keeps_existing(mock_info, db_session):
    _seed_stock(db_session, business="kept")
    stock = fetch_profile(db_session, "000001")
    assert stock.business == "kept"
```

- [ ] **Step 2: Run — confirm existing tests still pass structure-wise**

```bash
pytest tests/test_profile_collector.py -v
```

Expected: tests reference functions that may not exist yet — FAIL is OK here

- [ ] **Step 3: Replace profile.py**

```python
# backend/collectors/profile.py
import json
import logging
import threading
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.collectors.tushare_client import get_pro, to_ts_code
from backend.models import Stock

logger = logging.getLogger(__name__)
CACHE_TTL_DAYS = 30

# Concept reverse map: ts_code (with suffix) → list of concept names
_concept_map: dict[str, list[str]] = {}
_concept_map_lock = threading.Lock()
_concept_map_built = False


def _build_concept_map():
    global _concept_map_built
    pro = get_pro()
    try:
        concepts_df = pro.concept()
        if concepts_df is None or concepts_df.empty:
            return
        result: dict[str, list[str]] = {}
        for _, row in concepts_df.iterrows():
            cid = str(row.get("code") or "")
            cname = str(row.get("name") or "")
            if not cid:
                continue
            try:
                detail = pro.concept_detail(id=cid, fields="ts_code,name")
                if detail is None or detail.empty:
                    continue
                for _, drow in detail.iterrows():
                    ts = str(drow.get("ts_code") or "")
                    if ts:
                        result.setdefault(ts, []).append(cname)
            except Exception:
                pass
        with _concept_map_lock:
            _concept_map.update(result)
            _concept_map_built = True
    except Exception as e:
        logger.warning(f"concept map build failed: {e}")


def _ensure_concept_map():
    global _concept_map_built
    if not _concept_map_built:
        t = threading.Thread(target=_build_concept_map, daemon=True)
        t.start()


def _fetch_individual_info(code: str) -> dict | None:
    pro = get_pro()
    ts_code = to_ts_code(code)
    try:
        df = pro.stock_basic(
            ts_code=ts_code, list_status="L",
            fields="ts_code,name,industry,list_date,total_share,float_share"
        )
        if df is None or df.empty:
            return None
        row = df.iloc[0]
        total_share = _sf(row.get("total_share"))
        float_share = _sf(row.get("float_share"))
        list_date_raw = str(row.get("list_date") or "")
        list_date = f"{list_date_raw[:4]}-{list_date_raw[4:6]}-{list_date_raw[6:]}" if len(list_date_raw) == 8 else None
        return {
            "industry": str(row.get("industry") or ""),
            "total_share": round(total_share / 10000, 4) if total_share else None,   # 万股→亿股
            "float_share": round(float_share / 10000, 4) if float_share else None,
            "list_date": list_date,
        }
    except Exception as e:
        logger.warning(f"stock_basic failed for {code}: {e}")
        return None


def _fetch_business(session: Session, code: str) -> str | None:
    pro = get_pro()
    ts_code = to_ts_code(code)
    try:
        df = pro.stock_company(ts_code=ts_code, fields="ts_code,business_scope")
        if df is None or df.empty:
            return None
        return str(df.iloc[0].get("business_scope") or "")[:200] or None
    except Exception as e:
        logger.warning(f"stock_company failed for {code}: {e}")
        return None


def _fetch_concepts(code: str) -> list[str]:
    _ensure_concept_map()
    ts_code = to_ts_code(code)
    with _concept_map_lock:
        return _concept_map.get(ts_code, [])[:10]


def _cache_valid(stock: Stock) -> bool:
    if not stock.profile_updated_at:
        return False
    return stock.profile_updated_at > datetime.now() - timedelta(days=CACHE_TTL_DAYS)


def fetch_profile(session: Session, code: str) -> Stock | None:
    code = code.zfill(6)
    stock = session.get(Stock, code)
    if not stock:
        return None
    if _cache_valid(stock):
        return stock

    try:
        info = _fetch_individual_info(code)
    except Exception as e:
        logger.warning(f"profile fetch failed for {code}: {e}")
        return stock

    concepts = _fetch_concepts(code)
    business = _fetch_business(session, code)

    if info:
        if info.get("total_share") is not None:
            stock.total_share = info["total_share"]
        if info.get("float_share") is not None:
            stock.float_share = info["float_share"]
        if info.get("industry"):
            stock.industry = info["industry"]
        if info.get("list_date"):
            stock.list_date = info["list_date"]
    if concepts:
        stock.concepts = json.dumps(concepts, ensure_ascii=False)
    if business:
        stock.business = business

    stock.profile_updated_at = datetime.now()
    session.commit()
    return stock


def _sf(val):
    try:
        import math
        v = float(val)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 4: Run — confirm pass**

```bash
pytest tests/test_profile_collector.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/collectors/profile.py tests/test_profile_collector.py
git commit -m "feat: migrate profile collector to tushare stock_basic + stock_company + concept"
```

---

## Task 8: 迁移 trend.py

**Files:**
- Modify: `backend/collectors/trend.py`
- Modify: `tests/test_trend_collector.py`

- [ ] **Step 1: Update test to mock tushare instead of fetch_kline**

```python
# tests/test_trend_collector.py  — 完整替换
import json
import pandas as pd
from unittest.mock import patch, MagicMock
from backend.models import Stock, DailyData
from backend.collectors.trend import (
    _compute_returns,
    _detect_patterns,
    collect_trend,
)


def test_compute_returns_basic():
    closes = [100.0] * 60 + [105.0, 106.0, 107.0, 108.0, 110.0]
    r = _compute_returns(closes)
    assert round(r["return_5d"], 2) == 10.0
    assert round(r["return_20d"], 2) == 10.0
    assert round(r["return_60d"], 2) == 10.0


def test_compute_returns_insufficient_history_returns_none():
    closes = [100.0, 101.0, 102.0]
    r = _compute_returns(closes)
    assert r["return_5d"] is None
    assert r["return_20d"] is None
    assert r["return_60d"] is None


def test_detect_patterns_ma5_cross_up():
    d = {
        "ma5": 10.5, "ma13": 10.3, "prev_ma5": 10.1, "prev_ma13": 10.3,
        "volume_ratio": 1.0, "change_pct": 0.5,
        "macd_dif": 0.1, "macd_dea": 0.2,
    }
    tags = _detect_patterns(d, prev_macd_dif=0.0, prev_macd_dea=0.0)
    assert "MA5上穿MA13" in tags


def test_detect_patterns_ma5_cross_down():
    d = {"ma5": 10.1, "ma13": 10.3, "prev_ma5": 10.5, "prev_ma13": 10.3,
         "volume_ratio": 1.0, "change_pct": 0.0}
    tags = _detect_patterns(d, prev_macd_dif=None, prev_macd_dea=None)
    assert "MA5下穿MA13" in tags


def test_detect_patterns_volume_surge():
    d = {"ma5": 10.0, "ma13": 10.0, "prev_ma5": 10.0, "prev_ma13": 10.0,
         "volume_ratio": 2.5, "change_pct": 3.5}
    tags = _detect_patterns(d, prev_macd_dif=None, prev_macd_dea=None)
    assert "放量上攻" in tags


def test_detect_patterns_macd_gold_cross():
    d = {"ma5": 10.0, "ma13": 10.0, "prev_ma5": 10.0, "prev_ma13": 10.0,
         "volume_ratio": 1.0, "change_pct": 0.0,
         "macd_dif": 0.3, "macd_dea": 0.2}
    tags = _detect_patterns(d, prev_macd_dif=0.1, prev_macd_dea=0.2)
    assert "MACD金叉" in tags


@patch("backend.collectors.trend.get_pro")
def test_collect_trend_writes_daily_data(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro

    db_session.add(Stock(code="000001", name="平安银行", market="SZ", industry="银行", index_tags="[]"))
    today = "2026-04-25"
    db_session.add(DailyData(
        code="000001", date=today,
        ma5=10.5, ma13=10.3, prev_ma5=10.1, prev_ma13=10.3,
        volume_ratio=1.0, change_pct=0.5,
        macd_dif=0.1, macd_dea=0.2,
    ))
    db_session.commit()

    closes = [100.0] * 60 + [105.0, 106.0, 107.0, 108.0, 110.0]
    kline_df = pd.DataFrame({
        "ts_code": "000001.SZ",
        "trade_date": [f"20240{i+1:03d}" for i in range(len(closes))],
        "close": closes,
    })
    # ths_daily for industry changes
    ths_df = pd.DataFrame({
        "ts_code": "885096.TI",
        "trade_date": [f"20260{i+1:03d}" for i in range(25)],
        "close": [100.0 + i * 0.1 for i in range(25)],
    })

    mock_pro.daily.return_value = kline_df
    mock_pro.ths_daily.return_value = ths_df

    from backend.collectors import tushare_client
    tushare_client.INDUSTRY_TS_CODE_MAP["银行"] = "885096.TI"

    count = collect_trend(db_session, {"000001"}, today=today)

    assert count == 1
    row = db_session.query(DailyData).filter_by(code="000001", date=today).one()
    assert row.return_5d is not None
    tags = json.loads(row.pattern_tags or "[]")
    assert "MA5上穿MA13" in tags
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_trend_collector.py -v
```

Expected: FAIL (trend.py still uses fetch_kline)

- [ ] **Step 3: Replace trend.py**

```python
# backend/collectors/trend.py
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as _date, timedelta
from sqlalchemy.orm import Session

from backend.collectors.tushare_client import get_pro, to_ts_code, to_ts_date, INDUSTRY_TS_CODE_MAP
from backend.database import upsert
from backend.models import Stock, DailyData

logger = logging.getLogger(__name__)
_MAX_WORKERS = 10


def _compute_returns(closes: list[float]) -> dict:
    out = {"return_5d": None, "return_20d": None, "return_60d": None}
    if not closes:
        return out
    today = closes[-1]
    for window, key in [(5, "return_5d"), (20, "return_20d"), (60, "return_60d")]:
        if len(closes) > window:
            past = closes[-window - 1]
            if past:
                out[key] = round((today - past) / past * 100, 2)
    return out


def _detect_patterns(d: dict, prev_macd_dif, prev_macd_dea) -> list[str]:
    tags = []
    ma5, ma13 = d.get("ma5"), d.get("ma13")
    pma5, pma13 = d.get("prev_ma5"), d.get("prev_ma13")
    if None not in (ma5, ma13, pma5, pma13):
        if ma5 > ma13 and pma5 < pma13:
            tags.append("MA5上穿MA13")
        elif ma5 < ma13 and pma5 > pma13:
            tags.append("MA5下穿MA13")
    vr, chg = d.get("volume_ratio"), d.get("change_pct")
    if vr is not None and chg is not None and vr > 2 and chg > 3:
        tags.append("放量上攻")
    dif, dea = d.get("macd_dif"), d.get("macd_dea")
    if None not in (dif, dea, prev_macd_dif, prev_macd_dea):
        if dif > dea and prev_macd_dif <= prev_macd_dea:
            tags.append("MACD金叉")
    return tags


def _fetch_closes(code: str, today: str) -> list[float]:
    pro = get_pro()
    start = to_ts_date((_date.fromisoformat(today) - timedelta(days=95)).isoformat())
    try:
        df = pro.daily(ts_code=to_ts_code(code), start_date=start, end_date=to_ts_date(today),
                       fields="ts_code,trade_date,close")
        if df is None or df.empty:
            return []
        return df.sort_values("trade_date")["close"].astype(float).tolist()
    except Exception as e:
        logger.warning(f"trend kline failed for {code}: {e}")
        return []


def _fetch_industry_changes(industry: str, today: str) -> dict:
    null = {"change": None, "change_5d": None, "change_20d": None}
    if not industry:
        return null
    ts_code = INDUSTRY_TS_CODE_MAP.get(industry)
    if not ts_code:
        return null
    pro = get_pro()
    start = to_ts_date((_date.fromisoformat(today) - timedelta(days=35)).isoformat())
    try:
        df = pro.ths_daily(ts_code=ts_code, start_date=start, end_date=to_ts_date(today),
                           fields="ts_code,trade_date,close")
        if df is None or df.empty or len(df) < 2:
            return null
        closes = df.sort_values("trade_date")["close"].astype(float).tolist()
        today_c = closes[-1]
        def _chg(n):
            return round((today_c - closes[-n - 1]) / closes[-n - 1] * 100, 2) if len(closes) > n and closes[-n - 1] else None
        return {"change": _chg(1), "change_5d": _chg(5), "change_20d": _chg(20)}
    except Exception as e:
        logger.warning(f"ths_daily failed for {industry}: {e}")
        return null


class _IndustryCache:
    def __init__(self, today: str):
        self._cache: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._today = today

    def get(self, industry: str) -> dict:
        if not industry:
            return {"change": None, "change_5d": None, "change_20d": None}
        with self._lock:
            if industry not in self._cache:
                self._cache[industry] = _fetch_industry_changes(industry, self._today)
            return self._cache[industry]


def _process_one(code, today, daily_dict, industry, industry_cache):
    closes = _fetch_closes(code, today)
    returns = _compute_returns(closes)
    ichanges = industry_cache.get(industry)
    tags = _detect_patterns(daily_dict, daily_dict.get("macd_dif"), daily_dict.get("macd_dea"))
    return {
        "code": code, "date": today,
        **returns,
        "industry_change": ichanges["change"],
        "industry_change_5d": ichanges["change_5d"],
        "industry_change_20d": ichanges["change_20d"],
        "pattern_tags": json.dumps(tags, ensure_ascii=False),
    }


def collect_trend(session: Session, target_codes: set[str], today: str | None = None) -> int:
    today = today or _date.today().isoformat()
    stocks = {s.code: s for s in session.query(Stock).filter(Stock.code.in_(target_codes))}
    dailies = session.query(DailyData).filter(DailyData.date == today, DailyData.code.in_(target_codes)).all()
    daily_map = {d.code: d for d in dailies}
    industry_cache = _IndustryCache(today)

    tasks = []
    for code in target_codes:
        daily = daily_map.get(code)
        if not daily:
            continue
        stock = stocks.get(code)
        industry = stock.industry if stock else None
        tasks.append((code, today, {k: v for k, v in daily.__dict__.items() if not k.startswith("_")}, industry, industry_cache))

    results = []
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_process_one, *task): task[0] for task in tasks}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                logger.error(f"Trend failed for {futures[future]}: {e}")

    count = 0
    for record in results:
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"Trend upsert failed for {record.get('code')}: {e}")

    session.commit()
    logger.info(f"Trend data collected: {count} stocks")
    return count
```

- [ ] **Step 4: Run — confirm pass**

```bash
pytest tests/test_trend_collector.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/collectors/trend.py tests/test_trend_collector.py
git commit -m "feat: migrate trend collector to tushare daily + ths_daily"
```

---

## Task 9: 清理旧文件和依赖

**Files:**
- Delete: `backend/collectors/tencent_kline.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: 确认没有其他文件引用 tencent_kline**

```bash
grep -r "tencent_kline" /Users/anlory/Project/stock_score/backend/
```

Expected: 无输出（technical.py 和 trend.py 已不再引用）

- [ ] **Step 2: 删除 tencent_kline.py**

```bash
rm /Users/anlory/Project/stock_score/backend/collectors/tencent_kline.py
```

- [ ] **Step 3: 确认 akshare/efinance 没有其他引用**

```bash
grep -r "akshare\|efinance" /Users/anlory/Project/stock_score/backend/
```

Expected: 无输出

- [ ] **Step 4: 运行全部测试确认无断点**

```bash
pytest -v
```

Expected: 所有测试 PASS，无 import error

- [ ] **Step 5: 更新 CLAUDE.md 启动命令**

在 CLAUDE.md 的 `Commands` 部分，将 backend dev server 命令更新为：

```bash
TUSHARE_TOKEN=xxx uv run uvicorn backend.main:app --reload --port 8000
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: remove tencent_kline.py, akshare, efinance deps after tushare migration"
```
