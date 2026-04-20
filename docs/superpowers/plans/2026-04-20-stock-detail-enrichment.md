# Stock Detail Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add company profile, sector association, recent trend cards and a restructured four-section AI analysis to the stock detail page, backed by a layered caching strategy (lazy-loaded static profile + daily-collected dynamic data).

**Architecture:** Extend `Stock` and `DailyData` tables with new columns. Add two collectors: `profile.py` (lazy, 30-day TTL) and `trend.py` (runs in daily pipeline). Add a `GET /api/stocks/{code}/profile` endpoint; extend the existing `GET /api/scores/{code}` with a `trend_info` block; revise the AI prompt in `/api/analysis/{code}`. Frontend `StockDetail.vue` gets three new cards and a collapsible raw-indicator section.

**Tech Stack:** FastAPI + SQLAlchemy 2 (SQLite) + akshare + pywencai + httpx; Vue 3 + Vite + TailwindCSS; pytest.

**Spec:** `docs/superpowers/specs/2026-04-20-stock-detail-enrichment-design.md`

---

## File Structure

**Create:**
- `backend/collectors/profile.py` — lazy company profile collector
- `backend/collectors/trend.py` — daily trend / sector / pattern collector
- `tests/test_profile_collector.py`
- `tests/test_trend_collector.py`
- `tests/test_analysis_prompt.py`

**Modify:**
- `backend/models/stock.py` — add profile columns
- `backend/models/daily_data.py` — add trend columns
- `backend/database.py` — add SQLite `ADD COLUMN` migration helper; call from `init_db`
- `backend/routers/stocks.py` — add `/profile` endpoint
- `backend/routers/scores.py` — extend `get_stock_detail` with `trend_info`
- `backend/routers/analysis.py` — rewrite `_build_prompt` signature + content
- `backend/routers/trigger.py` — call `collect_trend` in pipeline
- `frontend/src/api/index.js` — add `getStockProfile`
- `frontend/src/views/StockDetail.vue` — add three cards, collapse raw, parallel fetch

---

## Task 1: Extend DB schema + SQLite migration helper

**Files:**
- Modify: `backend/models/stock.py`
- Modify: `backend/models/daily_data.py`
- Modify: `backend/database.py`
- Test: `tests/test_database.py`

- [ ] **Step 1: Add profile columns to Stock model**

Edit `backend/models/stock.py`:

```python
from sqlalchemy import Column, String, Boolean, DateTime, Float, Text
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Stock(Base):
    __tablename__ = "stocks"
    code = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    market = Column(String)
    is_watchlist = Column(Boolean, default=False)
    index_tags = Column(String, default="[]")
    # --- profile fields ---
    business = Column(Text)
    industry = Column(String)
    concepts = Column(Text, default="[]")          # JSON string
    total_share = Column(Float)                    # 亿股
    float_share = Column(Float)                    # 亿股
    list_date = Column(String)                     # YYYY-MM-DD
    profile_updated_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

- [ ] **Step 2: Add trend columns to DailyData model**

Edit `backend/models/daily_data.py` — append after `sector_heat_rank`:

```python
    return_5d = Column(Float)
    return_20d = Column(Float)
    return_60d = Column(Float)
    industry_change = Column(Float)
    industry_change_5d = Column(Float)
    industry_change_20d = Column(Float)
    pattern_tags = Column(Text, default="[]")      # JSON string
```

- [ ] **Step 3: Write failing test for migration helper**

Create/extend `tests/test_database.py`:

```python
import sqlite3
import tempfile
import os
from sqlalchemy import create_engine, text
from backend.database import _migrate_add_columns


def test_migrate_add_columns_adds_missing():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE stocks (code TEXT PRIMARY KEY, name TEXT)")
        conn.commit()
        conn.close()

        engine = create_engine(f"sqlite:///{path}")
        _migrate_add_columns(engine, "stocks", [
            ("industry", "VARCHAR"),
            ("total_share", "FLOAT"),
        ])

        with engine.connect() as c:
            cols = [row[1] for row in c.execute(text("PRAGMA table_info(stocks)"))]
        assert "industry" in cols
        assert "total_share" in cols


def test_migrate_add_columns_idempotent():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE stocks (code TEXT PRIMARY KEY, industry VARCHAR)")
        conn.commit()
        conn.close()

        engine = create_engine(f"sqlite:///{path}")
        # Running twice must not raise
        _migrate_add_columns(engine, "stocks", [("industry", "VARCHAR")])
        _migrate_add_columns(engine, "stocks", [("industry", "VARCHAR")])

        with engine.connect() as c:
            cols = [row[1] for row in c.execute(text("PRAGMA table_info(stocks)"))]
        assert cols.count("industry") == 1
    finally:
        os.unlink(path)
```

- [ ] **Step 4: Run test to verify failure**

Run: `pytest tests/test_database.py -v`
Expected: FAIL with `ImportError: cannot import name '_migrate_add_columns'`

- [ ] **Step 5: Implement migration helper + wire into init_db**

Edit `backend/database.py`:

```python
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from backend.config import DATABASE_URL, ensure_dirs
from backend.models import Base

ensure_dirs()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _migrate_add_columns(eng, table: str, columns: list[tuple[str, str]]):
    """SQLite-only: add columns that don't already exist. columns = [(name, sql_type), ...]."""
    with eng.connect() as conn:
        existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
        if not existing:
            return  # table doesn't exist yet; create_all will handle it
        for name, sql_type in columns:
            if name not in existing:
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {sql_type}'))
        conn.commit()


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_add_columns(engine, "stocks", [
        ("business", "TEXT"),
        ("industry", "VARCHAR"),
        ("concepts", "TEXT"),
        ("total_share", "FLOAT"),
        ("float_share", "FLOAT"),
        ("list_date", "VARCHAR"),
        ("profile_updated_at", "DATETIME"),
    ])
    _migrate_add_columns(engine, "daily_data", [
        ("return_5d", "FLOAT"),
        ("return_20d", "FLOAT"),
        ("return_60d", "FLOAT"),
        ("industry_change", "FLOAT"),
        ("industry_change_5d", "FLOAT"),
        ("industry_change_20d", "FLOAT"),
        ("pattern_tags", "TEXT"),
    ])
```

(Keep the existing `get_session`, `get_db_session`, `upsert`, `seed_strategies` functions unchanged.)

- [ ] **Step 6: Run tests to verify pass**

Run: `pytest tests/test_database.py -v`
Expected: PASS (both new tests; existing tests untouched)

Also run: `pytest tests/ -v`
Expected: all green

- [ ] **Step 7: Commit**

```bash
git add backend/models/stock.py backend/models/daily_data.py backend/database.py tests/test_database.py
git commit -m "feat(db): extend Stock/DailyData schema with profile and trend columns"
```

---

## Task 2: Profile collector + `/api/stocks/{code}/profile`

**Files:**
- Create: `backend/collectors/profile.py`
- Modify: `backend/routers/stocks.py`
- Test: `tests/test_profile_collector.py`

- [ ] **Step 1: Write failing test for fresh-fetch path**

Create `tests/test_profile_collector.py`:

```python
import json
from datetime import datetime, timedelta
from unittest.mock import patch
import pandas as pd
from backend.models import Stock
from backend.collectors.profile import fetch_profile


def _seed_stock(session, code="000001", **kw):
    defaults = dict(code=code, name="平安银行", market="SZ", is_watchlist=False, index_tags="[]")
    defaults.update(kw)
    session.add(Stock(**defaults))
    session.commit()


@patch("backend.collectors.profile._fetch_individual_info")
@patch("backend.collectors.profile._fetch_business")
@patch("backend.collectors.profile._fetch_concepts")
def test_fetch_profile_populates_all_fields(mock_concepts, mock_business, mock_info, db_session):
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


@patch("backend.collectors.profile._fetch_individual_info")
@patch("backend.collectors.profile._fetch_business")
@patch("backend.collectors.profile._fetch_concepts")
def test_fetch_profile_expired_cache_refetches(mock_concepts, mock_business, mock_info, db_session):
    _seed_stock(
        db_session,
        industry="银行",
        business="stale",
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
    assert stock.business == "kept"  # did not overwrite
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_profile_collector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.collectors.profile'`

- [ ] **Step 3: Implement collector**

Create `backend/collectors/profile.py`:

```python
import json
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.models import Stock

logger = logging.getLogger(__name__)

CACHE_TTL_DAYS = 30


def _fetch_individual_info(code: str) -> dict:
    """Return {industry, total_share, float_share, list_date} from akshare."""
    import akshare as ak
    df = ak.stock_individual_info_em(symbol=code)
    # DataFrame with columns [item, value]
    kv = dict(zip(df["item"], df["value"]))
    def _to_float(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    list_date = kv.get("上市时间")
    if list_date and len(str(list_date)) == 8:
        s = str(list_date)
        list_date = f"{s[0:4]}-{s[4:6]}-{s[6:8]}"

    # akshare reports shares in 股, convert to 亿股
    total = _to_float(kv.get("总股本"))
    floatv = _to_float(kv.get("流通股"))
    return {
        "industry": kv.get("行业"),
        "total_share": round(total / 1e8, 4) if total else None,
        "float_share": round(floatv / 1e8, 4) if floatv else None,
        "list_date": list_date,
    }


def _fetch_business(code: str) -> str | None:
    """Return a short business description (<=200 chars) via akshare."""
    import akshare as ak
    try:
        df = ak.stock_zyjs_ths(symbol=code)
        if df is None or df.empty:
            return None
        # Columns vary; pick the first string-heavy cell in the 主营业务 row
        for col in ("主营业务", "产品名称", "经营范围"):
            if col in df.columns:
                val = df[col].iloc[0]
                if val:
                    s = str(val).strip()
                    return s[:200]
        return None
    except Exception as e:
        logger.warning(f"business fetch failed for {code}: {e}")
        return None


def _fetch_concepts(code: str) -> list[str]:
    """Return list of concept board names via pywencai; empty on failure."""
    try:
        from backend.collectors.base import query_wencai
        df = query_wencai(f"{code} 所属概念板块")
        if df is None or df.empty:
            return []
        for col in df.columns:
            if "概念" in col or "板块" in col:
                raw = df[col].iloc[0]
                if isinstance(raw, str):
                    parts = [p.strip() for p in raw.replace("，", ",").split(",") if p.strip()]
                    return parts[:10]
                if isinstance(raw, list):
                    return [str(x) for x in raw[:10]]
        return []
    except Exception as e:
        logger.warning(f"concepts fetch failed for {code}: {e}")
        return []


def _cache_valid(stock: Stock) -> bool:
    if not stock.profile_updated_at:
        return False
    return stock.profile_updated_at > datetime.now() - timedelta(days=CACHE_TTL_DAYS)


def fetch_profile(session: Session, code: str) -> Stock | None:
    """Return Stock with profile fields populated. Uses 30-day cache."""
    code = code.zfill(6)
    stock = session.get(Stock, code)
    if not stock:
        return None
    if _cache_valid(stock):
        return stock

    try:
        info = _fetch_individual_info(code)
        business = _fetch_business(code)
        concepts = _fetch_concepts(code)
    except Exception as e:
        logger.error(f"profile fetch failed for {code}: {e}")
        return stock  # keep existing values

    if info.get("industry") is not None:
        stock.industry = info["industry"]
    if info.get("total_share") is not None:
        stock.total_share = info["total_share"]
    if info.get("float_share") is not None:
        stock.float_share = info["float_share"]
    if info.get("list_date") is not None:
        stock.list_date = info["list_date"]
    if business:
        stock.business = business
    if concepts:
        stock.concepts = json.dumps(concepts, ensure_ascii=False)
    stock.profile_updated_at = datetime.now()
    session.commit()
    return stock
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_profile_collector.py -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Add `/profile` endpoint**

Edit `backend/routers/stocks.py` — append after `remove_from_watchlist`:

```python
import json
from backend.collectors.profile import fetch_profile


@router.get("/{code}/profile")
def get_stock_profile(code: str, session: Session = Depends(get_session)):
    code = code.zfill(6)
    stock = fetch_profile(session, code)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
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
        "list_date": stock.list_date,
    }
```

- [ ] **Step 6: Smoke-test the endpoint manually**

Start the server in one terminal: `uvicorn backend.main:app --reload`

In another: `curl http://localhost:8000/api/stocks/000001/profile | jq .`

Expected: JSON with `business`, `industry`, `concepts` (may be empty if akshare blocked — that's acceptable, verify no 5xx).

- [ ] **Step 7: Commit**

```bash
git add backend/collectors/profile.py backend/routers/stocks.py tests/test_profile_collector.py
git commit -m "feat(profile): add lazy-loaded company profile collector and endpoint"
```

---

## Task 3: Trend collector (returns + industry + pattern tags)

**Files:**
- Create: `backend/collectors/trend.py`
- Test: `tests/test_trend_collector.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_trend_collector.py`:

```python
import json
from unittest.mock import patch
from backend.models import Stock, DailyData
from backend.collectors.trend import (
    _compute_returns,
    _detect_patterns,
    collect_trend,
)


def test_compute_returns_basic():
    # close prices chronological, oldest first. Today's close = 110, 5 days ago = 100.
    closes = [100.0] * 60 + [105.0, 106.0, 107.0, 108.0, 110.0]  # length 65
    r = _compute_returns(closes)
    assert round(r["return_5d"], 2) == 10.0   # (110-100)/100
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


@patch("backend.collectors.trend._fetch_industry_changes")
@patch("backend.collectors.trend.fetch_kline")
def test_collect_trend_writes_daily_data(mock_kline, mock_industry, db_session):
    db_session.add(Stock(code="000001", name="平安银行", market="SZ", industry="银行", index_tags="[]"))
    today = "2026-04-20"
    db_session.add(DailyData(
        code="000001", date=today,
        ma5=10.5, ma13=10.3, prev_ma5=10.1, prev_ma13=10.3,
        volume_ratio=1.0, change_pct=0.5,
        macd_dif=0.1, macd_dea=0.2,
    ))
    db_session.commit()

    closes = [100.0] * 60 + [105.0, 106.0, 107.0, 108.0, 110.0]
    mock_kline.return_value = [{"date": f"2026-01-{i%30+1:02d}", "close": c}
                               for i, c in enumerate(closes)]
    mock_industry.return_value = {"change": 0.8, "change_5d": 2.1, "change_20d": -0.5}

    count = collect_trend(db_session, {"000001"}, today=today)

    assert count == 1
    row = db_session.query(DailyData).filter_by(code="000001", date=today).one()
    assert row.return_5d is not None
    assert row.industry_change == 0.8
    tags = json.loads(row.pattern_tags or "[]")
    assert "MA5上穿MA13" in tags
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_trend_collector.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement collector**

Create `backend/collectors/trend.py`:

```python
import json
import logging
from datetime import date as _date
from sqlalchemy.orm import Session
from backend.models import Stock, DailyData
from backend.database import upsert
from backend.collectors.tencent_kline import fetch_kline

logger = logging.getLogger(__name__)


def _compute_returns(closes: list[float]) -> dict:
    """Given chronological closes (oldest first), compute 5/20/60-day pct changes."""
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


def _fetch_industry_changes(industry: str) -> dict:
    """Return {change, change_5d, change_20d} for the given industry board."""
    if not industry:
        return {"change": None, "change_5d": None, "change_20d": None}
    try:
        import akshare as ak
        df = ak.stock_board_industry_hist_em(symbol=industry, period="daily", adjust="")
        if df is None or df.empty or len(df) < 2:
            return {"change": None, "change_5d": None, "change_20d": None}
        closes = df["收盘"].astype(float).tolist() if "收盘" in df.columns else []
        if not closes:
            return {"change": None, "change_5d": None, "change_20d": None}
        today = closes[-1]
        def _chg(n):
            return round((today - closes[-n-1]) / closes[-n-1] * 100, 2) if len(closes) > n and closes[-n-1] else None
        return {"change": _chg(1), "change_5d": _chg(5), "change_20d": _chg(20)}
    except Exception as e:
        logger.warning(f"industry hist failed for {industry}: {e}")
        return {"change": None, "change_5d": None, "change_20d": None}


def _prev_macd(session: Session, code: str, today: str) -> tuple:
    """Fetch yesterday's DailyData macd_dif/dea for MACD cross detection."""
    row = (
        session.query(DailyData)
        .filter(DailyData.code == code, DailyData.date < today)
        .order_by(DailyData.date.desc())
        .first()
    )
    if not row:
        return (None, None)
    return (row.macd_dif, row.macd_dea)


def collect_trend(session: Session, target_codes: set[str], today: str | None = None) -> int:
    """Populate trend fields on DailyData for the given codes. Returns count written."""
    today = today or _date.today().isoformat()
    stocks = {s.code: s for s in session.query(Stock).filter(Stock.code.in_(target_codes))}
    industry_cache: dict[str, dict] = {}
    count = 0

    for code in target_codes:
        stock = stocks.get(code)
        daily = session.query(DailyData).filter_by(code=code, date=today).first()
        if not daily:
            continue

        # Returns
        try:
            kline = fetch_kline(code, days=65)
            closes = [float(row["close"]) for row in kline]
        except Exception as e:
            logger.warning(f"kline failed for {code}: {e}")
            closes = []
        returns = _compute_returns(closes)

        # Industry
        industry = stock.industry if stock else None
        if industry:
            if industry not in industry_cache:
                industry_cache[industry] = _fetch_industry_changes(industry)
            ichanges = industry_cache[industry]
        else:
            ichanges = {"change": None, "change_5d": None, "change_20d": None}

        # Patterns
        prev_dif, prev_dea = _prev_macd(session, code, today)
        tags = _detect_patterns(daily.__dict__, prev_dif, prev_dea)

        upsert(session, DailyData, {
            "code": code, "date": today,
            **returns,
            "industry_change": ichanges["change"],
            "industry_change_5d": ichanges["change_5d"],
            "industry_change_20d": ichanges["change_20d"],
            "pattern_tags": json.dumps(tags, ensure_ascii=False),
        }, ["code", "date"])
        count += 1

    session.commit()
    logger.info(f"Trend data collected: {count} stocks")
    return count
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_trend_collector.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/collectors/trend.py tests/test_trend_collector.py
git commit -m "feat(trend): add daily trend collector for returns, industry change, pattern tags"
```

---

## Task 4: Wire trend into pipeline + extend `/api/scores/{code}`

**Files:**
- Modify: `backend/routers/trigger.py`
- Modify: `backend/routers/scores.py`

- [ ] **Step 1: Add `collect_trend` to pipeline**

Edit `backend/routers/trigger.py` — import and call after `collect_market_heat`:

```python
from backend.collectors.trend import collect_trend
```

Inside `_run_pipeline`, right before `engine = ScoreEngine()`:

```python
        collect_trend(session, codes)
```

- [ ] **Step 2: Extend stock detail response**

Edit `backend/routers/scores.py::get_stock_detail` — replace the return statement:

```python
import json as _json

    trend_info = None
    if daily:
        try:
            pattern_tags = _json.loads(daily.pattern_tags or "[]")
        except (ValueError, TypeError):
            pattern_tags = []
        trend_info = {
            "return_5d": daily.return_5d,
            "return_20d": daily.return_20d,
            "return_60d": daily.return_60d,
            "industry_change": daily.industry_change,
            "industry_change_5d": daily.industry_change_5d,
            "industry_change_20d": daily.industry_change_20d,
            "pattern_tags": pattern_tags,
        }

    return {
        "code": code,
        "name": stock.name if stock else code,
        "short_term": _score_dict(short) if short else None,
        "trend": _score_dict(trend) if trend else None,
        "scores": _score_dict(trend) if trend else (_score_dict(short) if short else {}),
        "raw": {k: v for k, v in daily.__dict__.items() if not k.startswith("_")} if daily else {},
        "ai_analysis": daily.ai_analysis if daily else None,
        "trend_info": trend_info,
    }
```

(Put the `import json as _json` at the module top, not inside the function.)

- [ ] **Step 3: Smoke-test**

Start server. Run: `curl http://localhost:8000/api/scores/000001 | jq .trend_info`

Expected: object with `return_5d`, `pattern_tags` (may be null values until a pipeline run finishes — acceptable here, full integration will follow in manual verification).

- [ ] **Step 4: Commit**

```bash
git add backend/routers/trigger.py backend/routers/scores.py
git commit -m "feat(api): wire trend collector into pipeline and expose trend_info"
```

---

## Task 5: Revise AI analysis prompt

**Files:**
- Modify: `backend/routers/analysis.py`
- Test: `tests/test_analysis_prompt.py`

- [ ] **Step 1: Write failing test for new prompt content**

Create `tests/test_analysis_prompt.py`:

```python
from backend.routers.analysis import _build_prompt


def test_prompt_includes_all_context():
    prompt = _build_prompt(
        stock_name="平安银行",
        stock_code="000001",
        scores={"total": 72, "technical": 75, "capital": 68, "fundamental": 70, "news": 60, "heat": 80},
        profile={
            "business": "主要提供银行业务",
            "industry": "银行",
            "concepts": ["金融改革", "大金融"],
        },
        trend_info={
            "return_5d": 3.2, "return_20d": -1.1, "return_60d": 12.5,
            "industry_change": 0.8, "industry_change_5d": 2.1, "industry_change_20d": -0.5,
            "pattern_tags": ["MA5上穿MA13", "放量上攻"],
        },
    )
    assert "平安银行" in prompt
    assert "银行业务" in prompt
    assert "金融改革" in prompt
    assert "MA5上穿MA13" in prompt
    assert "3.2" in prompt
    # Structure: four-section output
    assert "公司概况" in prompt
    assert "板块关联" in prompt
    assert "近期走势" in prompt
    assert "综合研判" in prompt


def test_prompt_handles_missing_profile_and_trend():
    # Should not crash when profile/trend are None
    prompt = _build_prompt(
        stock_name="某股",
        stock_code="000999",
        scores={"total": 50, "technical": 50, "capital": 50, "fundamental": 50, "news": 50, "heat": 50},
        profile=None,
        trend_info=None,
    )
    assert "某股" in prompt
    assert "公司概况" in prompt
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_analysis_prompt.py -v`
Expected: FAIL — `_build_prompt` signature doesn't accept profile/trend_info.

- [ ] **Step 3: Update `_build_prompt` + caller**

Edit `backend/routers/analysis.py`:

```python
def _build_prompt(stock_name, stock_code, scores, profile=None, trend_info=None):
    dims = {
        "technical": "技术面", "capital": "资金面",
        "fundamental": "基本面", "news": "消息面", "heat": "市场热度",
    }
    score_lines = "\n".join(f"- {label}：{scores.get(k, 'N/A')}分" for k, label in dims.items())

    profile_block = "（暂无公司资料）"
    if profile:
        parts = []
        if profile.get("business"):
            parts.append(f"主营业务：{profile['business']}")
        if profile.get("industry"):
            parts.append(f"所属行业：{profile['industry']}")
        concepts = profile.get("concepts") or []
        if concepts:
            parts.append(f"概念板块：{', '.join(concepts)}")
        if parts:
            profile_block = "\n".join(parts)

    trend_block = "（暂无近期走势数据）"
    if trend_info:
        lines = []
        r5, r20, r60 = trend_info.get("return_5d"), trend_info.get("return_20d"), trend_info.get("return_60d")
        if any(v is not None for v in (r5, r20, r60)):
            lines.append(f"个股涨跌：近5日 {r5}%，近20日 {r20}%，近60日 {r60}%")
        ic, ic5, ic20 = trend_info.get("industry_change"), trend_info.get("industry_change_5d"), trend_info.get("industry_change_20d")
        if any(v is not None for v in (ic, ic5, ic20)):
            lines.append(f"行业涨跌：今日 {ic}%，近5日 {ic5}%，近20日 {ic20}%")
        tags = trend_info.get("pattern_tags") or []
        if tags:
            lines.append(f"技术形态：{', '.join(tags)}")
        if lines:
            trend_block = "\n".join(lines)

    return f"""你是一位专业的A股分析师，请基于以下信息对股票出具结构化研判。

股票：{stock_name}({stock_code})
综合评分：{scores.get('total', 'N/A')}分（满分100）

各维度评分：
{score_lines}

公司与板块：
{profile_block}

近期表现：
{trend_block}

请用中文 markdown 输出，严格按以下 4 段结构，每段用 `## 标题` 开头：

## 公司概况
一句话概括主营业务与所处行业地位。

## 板块关联
基于所属行业/概念，结合板块近期表现，分析板块强弱对个股的影响（2-3句）。

## 近期走势
结合 5/20/60 日涨跌与技术形态标签，判断当前走势位置（2-3句）。

## 综合研判
给出多空判断、核心逻辑，以及短线与趋势两个视角的操作建议。

全文不超过 600 字，语言简洁有力，避免空话。"""
```

Then update `analyze_stock` to pass profile + trend:

```python
    # ... after `daily = session.query(DailyData)...`
    profile_payload = None
    if stock:
        try:
            import json as _json
            concepts = _json.loads(stock.concepts or "[]")
        except Exception:
            concepts = []
        profile_payload = {
            "business": stock.business,
            "industry": stock.industry,
            "concepts": concepts,
        }

    trend_info_payload = None
    if daily:
        try:
            import json as _json
            pattern_tags = _json.loads(daily.pattern_tags or "[]")
        except Exception:
            pattern_tags = []
        trend_info_payload = {
            "return_5d": daily.return_5d, "return_20d": daily.return_20d, "return_60d": daily.return_60d,
            "industry_change": daily.industry_change,
            "industry_change_5d": daily.industry_change_5d,
            "industry_change_20d": daily.industry_change_20d,
            "pattern_tags": pattern_tags,
        }

    prompt = _build_prompt(stock_name, code, scores, profile_payload, trend_info_payload)
```

Also bump `max_tokens` to `6144` to allow the longer answer.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_analysis_prompt.py -v`
Expected: both tests PASS.

Run: `pytest tests/ -v`
Expected: full suite PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/analysis.py tests/test_analysis_prompt.py
git commit -m "feat(ai): restructure AI prompt into four sections with profile+trend context"
```

---

## Task 6: Frontend — API client + three new cards + collapse raw

**Files:**
- Modify: `frontend/src/api/index.js`
- Modify: `frontend/src/views/StockDetail.vue`

- [ ] **Step 1: Add API client method**

Edit `frontend/src/api/index.js` — append:

```javascript
export const getStockProfile = (code) =>
  api.get(`/stocks/${code}/profile`).then(r => r.data)
```

- [ ] **Step 2: Rewrite StockDetail.vue**

Replace `frontend/src/views/StockDetail.vue` with:

```vue
<template>
  <div class="p-6 max-w-5xl mx-auto">
    <button @click="$router.back()" class="text-gray-400 hover:text-white mb-4 text-sm">← 返回</button>
    <div v-if="!data" class="space-y-4 py-6">
      <div class="flex items-center gap-4">
        <div class="h-8 w-40 rounded bg-gray-800 animate-pulse"></div>
        <div class="h-5 w-20 rounded bg-gray-800 animate-pulse"></div>
      </div>
      <div class="h-28 rounded-lg bg-gray-800 animate-pulse"></div>
      <div class="h-20 rounded-lg bg-gray-800 animate-pulse"></div>
      <div class="h-20 rounded-lg bg-gray-800 animate-pulse"></div>
    </div>
    <template v-else>
      <div class="flex items-center gap-4 mb-6">
        <h1 class="text-2xl font-bold">{{ data.name }}</h1>
        <span class="font-mono text-gray-400">{{ data.code }}</span>
        <div class="ml-auto flex gap-3">
          <span v-if="data.short_term" class="bg-amber-900/40 text-amber-300 border border-amber-800/40 px-3 py-1 rounded-full font-mono font-bold text-lg">
            短线 {{ data.short_term.total }} 分
          </span>
          <span v-if="data.trend" class="bg-blue-900/40 text-blue-300 border border-blue-800/40 px-3 py-1 rounded-full font-mono font-bold text-lg">
            趋势 {{ data.trend.total }} 分
          </span>
        </div>
      </div>

      <!-- 公司概况 -->
      <section class="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <h2 class="text-sm text-gray-400 font-semibold mb-3">公司概况</h2>
        <div v-if="profile" class="space-y-3">
          <div class="flex flex-wrap gap-2">
            <span v-if="profile.industry" class="bg-blue-900/40 text-blue-300 text-xs px-2 py-0.5 rounded">
              {{ profile.industry }}
            </span>
            <span v-for="c in profile.concepts" :key="c" class="bg-gray-800 text-xs px-2 py-0.5 rounded text-gray-300">
              {{ c }}
            </span>
          </div>
          <div v-if="profile.business" class="text-sm text-gray-200 leading-relaxed">
            <span :class="{ 'line-clamp-2': !showFullBiz }">{{ profile.business }}</span>
            <button v-if="profile.business.length > 80"
              @click="showFullBiz = !showFullBiz"
              class="ml-2 text-blue-400 text-xs">{{ showFullBiz ? '收起' : '展开' }}</button>
          </div>
          <div class="text-xs text-gray-500 flex gap-4 flex-wrap">
            <span v-if="profile.list_date">上市：{{ profile.list_date }}</span>
            <span v-if="profile.total_share">总股本：{{ profile.total_share }} 亿</span>
            <span v-if="profile.float_share">流通股本：{{ profile.float_share }} 亿</span>
          </div>
        </div>
        <div v-else class="text-gray-600 text-xs py-2">暂无公司资料</div>
      </section>

      <!-- 板块关联 -->
      <section class="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <h2 class="text-sm text-gray-400 font-semibold mb-3">板块关联</h2>
        <div v-if="profile?.industry && trendInfo" class="flex flex-wrap items-center gap-4 text-sm">
          <span class="text-gray-200">{{ profile.industry }}</span>
          <span>今日 <span :class="pctColor(trendInfo.industry_change)" class="font-mono">{{ fmtPct(trendInfo.industry_change) }}</span></span>
          <span>近5日 <span :class="pctColor(trendInfo.industry_change_5d)" class="font-mono">{{ fmtPct(trendInfo.industry_change_5d) }}</span></span>
          <span>近20日 <span :class="pctColor(trendInfo.industry_change_20d)" class="font-mono">{{ fmtPct(trendInfo.industry_change_20d) }}</span></span>
        </div>
        <div v-else class="text-gray-600 text-xs py-2">暂无板块数据</div>
      </section>

      <!-- 近期趋势 -->
      <section class="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <h2 class="text-sm text-gray-400 font-semibold mb-3">近期趋势</h2>
        <div v-if="trendInfo" class="space-y-3">
          <div class="flex flex-wrap gap-6 text-sm">
            <span>近5日 <span :class="pctColor(trendInfo.return_5d)" class="font-mono font-semibold">{{ fmtPct(trendInfo.return_5d) }}</span></span>
            <span>近20日 <span :class="pctColor(trendInfo.return_20d)" class="font-mono font-semibold">{{ fmtPct(trendInfo.return_20d) }}</span></span>
            <span>近60日 <span :class="pctColor(trendInfo.return_60d)" class="font-mono font-semibold">{{ fmtPct(trendInfo.return_60d) }}</span></span>
          </div>
          <div v-if="trendInfo.pattern_tags?.length" class="flex flex-wrap gap-2">
            <span v-for="t in trendInfo.pattern_tags" :key="t"
              class="bg-amber-900/30 text-amber-300 text-xs px-2 py-0.5 rounded border border-amber-800/30">
              {{ t }}
            </span>
          </div>
        </div>
        <div v-else class="text-gray-600 text-xs py-2">暂无近期趋势数据</div>
      </section>

      <!-- AI 综合研判 -->
      <section class="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm text-gray-400 font-semibold">AI 综合研判</span>
          <button @click="fetchAnalysis" :disabled="aiLoading"
            class="px-3 py-1 rounded text-xs transition-colors"
            :class="aiLoading ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-blue-800 text-white hover:bg-blue-700'"
          >{{ aiLoading ? '分析中...' : (data.ai_analysis ? '重新分析' : '开始分析') }}</button>
        </div>
        <div v-if="aiLoading" class="text-gray-500 text-center py-4 text-xs">AI 正在分析中...</div>
        <div v-else-if="aiError" class="text-red-400 text-xs py-1">{{ aiError }}</div>
        <div v-else-if="displayAnalysis" class="ai-analysis text-gray-200 text-sm leading-relaxed" v-html="displayAnalysis"></div>
        <div v-else class="text-gray-600 text-center py-4 text-xs">点击"开始分析"获取 AI 综合研判</div>
      </section>

      <!-- 雷达图 + 五维评分 -->
      <div class="flex gap-6 flex-wrap mb-4">
        <RadarChart :scores="data.scores" />
        <div class="flex-1 grid grid-cols-1 gap-3 min-w-[260px]">
          <div v-for="dim in dimensions" :key="dim.key"
            class="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 flex items-center justify-between">
            <span class="text-gray-400 text-sm">{{ dim.label }}</span>
            <span class="font-mono font-semibold text-lg" :class="scoreColor(data.scores?.[dim.key])">
              {{ data.scores?.[dim.key] ?? '-' }}
            </span>
          </div>
        </div>
      </div>

      <!-- K线图 -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <h2 class="text-sm text-gray-400 mb-3 font-semibold">K线图 · TradingView</h2>
        <TradingViewChart :code="route.params.code" />
      </div>

      <!-- 原始指标（默认折叠） -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <button @click="showRaw = !showRaw" class="w-full flex items-center justify-between text-sm text-gray-400 font-semibold">
          <span>原始指标数据</span>
          <span class="text-xs">{{ showRaw ? '收起 ▲' : '展开 ▼' }}</span>
        </button>
        <div v-if="showRaw" class="grid grid-cols-3 gap-2 text-xs font-mono mt-3">
          <div v-for="(val, key) in displayRaw" :key="key" class="flex justify-between border-b border-gray-800/50 py-1">
            <span class="text-gray-500">{{ key }}</span>
            <span class="text-gray-200">{{ val ?? '-' }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import RadarChart from '../components/RadarChart.vue'
import TradingViewChart from '../components/TradingViewChart.vue'
import { getStockDetail, getStockProfile, getAnalysis } from '../api'

function preprocessBold(text) {
  return text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
}

const route = useRoute()
const data = ref(null)
const profile = ref(null)
const aiResult = ref('')
const aiLoading = ref(false)
const aiError = ref('')
const showFullBiz = ref(false)
const showRaw = ref(false)

const trendInfo = computed(() => data.value?.trend_info || null)
const displayAnalysis = computed(() => {
  const text = aiResult.value || data.value?.ai_analysis || ''
  return text ? marked.parse(preprocessBold(text)) : ''
})

const dimensions = [
  { key: 'technical', label: '技术面' },
  { key: 'capital', label: '资金面' },
  { key: 'fundamental', label: '基本面' },
  { key: 'news', label: '消息面' },
  { key: 'heat', label: '市场热度' },
]
const SKIP = new Set(['code', 'date', '_sa_instance_state', 'ai_analysis',
  'return_5d', 'return_20d', 'return_60d',
  'industry_change', 'industry_change_5d', 'industry_change_20d', 'pattern_tags'])
const displayRaw = computed(() => {
  if (!data.value?.raw) return {}
  return Object.fromEntries(
    Object.entries(data.value.raw).filter(([k, v]) => !SKIP.has(k) && v != null)
  )
})

function scoreColor(s) {
  if (!s) return 'text-gray-400'
  if (s >= 75) return 'text-green-400'
  if (s >= 50) return 'text-yellow-400'
  return 'text-red-400'
}
function pctColor(v) {
  if (v === null || v === undefined) return 'text-gray-500'
  return v > 0 ? 'text-red-400' : (v < 0 ? 'text-green-400' : 'text-gray-300')
}
function fmtPct(v) {
  if (v === null || v === undefined) return '-'
  const sign = v > 0 ? '+' : ''
  return `${sign}${v.toFixed(2)}%`
}

async function load() {
  const [detail, prof] = await Promise.allSettled([
    getStockDetail(route.params.code),
    getStockProfile(route.params.code),
  ])
  if (detail.status === 'fulfilled') data.value = detail.value
  if (prof.status === 'fulfilled') profile.value = prof.value
  aiResult.value = ''
  aiError.value = ''
}
async function fetchAnalysis() {
  aiError.value = ''
  aiLoading.value = true
  try {
    const res = await getAnalysis(route.params.code)
    aiResult.value = res.analysis
  } catch (e) {
    aiError.value = e.response?.data?.detail || 'AI 分析请求失败'
  }
  aiLoading.value = false
}
onMounted(load)
</script>

<style scoped>
.ai-analysis :deep(p) { margin: 0.4em 0; }
.ai-analysis :deep(ul), .ai-analysis :deep(ol) { margin: 0.4em 0; padding-left: 1.5em; }
.ai-analysis :deep(li) { margin: 0.2em 0; }
.ai-analysis :deep(strong) { color: #93c5fd; font-weight: 600; }
.ai-analysis :deep(h1), .ai-analysis :deep(h2), .ai-analysis :deep(h3) {
  color: #e5e7eb; font-weight: 700; margin: 0.6em 0 0.3em; font-size: 0.95rem;
}
.line-clamp-2 {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
</style>
```

- [ ] **Step 3: Manual browser verification**

Start frontend: `cd frontend && npm run dev`
Start backend: `uvicorn backend.main:app --reload`

Open a stock detail page in browser. Verify:
1. Three new cards render in order: 公司概况 / 板块关联 / 近期趋势
2. If profile missing (new stock), cards show "暂无..." instead of crashing
3. Raw indicator section is collapsed by default; clicking expands
4. Click "开始分析" → AI returns four `## 标题` sections
5. Percentages colored red for positive, green for negative (A 股 convention)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/index.js frontend/src/views/StockDetail.vue
git commit -m "feat(ui): restructure stock detail page with profile, sector, trend cards"
```

---

## Self-Review

1. **Spec coverage:**
   - Stock/DailyData schema → Task 1 ✓
   - Profile collector + endpoint → Task 2 ✓
   - Trend collector → Task 3 ✓
   - Pipeline wiring + `/api/scores/{code}` extension → Task 4 ✓
   - AI prompt revamp → Task 5 ✓
   - Frontend three cards + collapse raw → Task 6 ✓

2. **Placeholder scan:** No TBDs, no "implement later", every code block is complete. ✓

3. **Type consistency:**
   - `fetch_profile(session, code) -> Stock | None` — used in Task 2 step 5 ✓
   - `collect_trend(session, target_codes: set[str], today: str | None = None) -> int` — callers pass `codes` (set of str) ✓
   - Response field `trend_info` — Task 4 emits, Task 6 consumes via `data.value?.trend_info` ✓
   - `_build_prompt(stock_name, stock_code, scores, profile=None, trend_info=None)` — caller passes both ✓
   - `concepts` stored as JSON string in DB, parsed to list in API responses (Task 2 endpoint & Task 5 analysis) ✓
