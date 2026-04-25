# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Backend
uv sync                                    # install deps
TUSHARE_TOKEN=xxx uv run uvicorn backend.main:app --reload --port 8000   # dev server
TUSHARE_TOKEN=xxx GLM_API_KEY=xxx uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000  # prod with AI

# Frontend
cd frontend && npm install && npm run dev  # dev (proxies /api to :8000)
cd frontend && npm run build               # build to frontend/dist/

# Tests
pytest                                     # all tests
pytest tests/test_engine.py -v             # single file
pytest tests/test_scorers.py::test_x -v    # single test

# Both at once
./dev.sh                                   # runs frontend + backend concurrently
```

## Architecture

**Stack**: FastAPI + SQLAlchemy (SQLite) backend, Vue 3 + Vite + Tailwind CSS v4 + ECharts frontend. Python 3.12, uv for package management.

### Data Pipeline

`trigger.py` orchestrates the full pipeline; `scheduler.py` runs it daily at 16:00:

1. **Universe sync** (`collectors/universe.py`) — fetches index components (HS300, CS500, ChiNext) + hot sector stocks, populates `stocks` table
2. **6 collectors run in parallel** via `ThreadPoolExecutor` — each takes a session + set of stock codes, writes to `daily_data` table:
   - `technical.py` — Tushare daily K-line → pandas_ta (MACD, RSI, KDJ, BOLL, MAs)
   - `capital.py` — East Money fund flow API (httpx, parallel per-stock)
   - `fundamental.py` — pywencai (PE, PB, ROE, profit growth) — uses shared `collect_wencai_fields()` from `base.py`
   - `news.py` — pywencai (report count, rating) — same shared pattern
   - `market_heat.py` — pywencai (change%, turnover, volume ratio)
   - `trend.py` — daily returns, industry change, pattern tags
3. **ScoreEngine** (`engine.py`) — scorers return raw 0-100 values per dimension; engine percentile-ranks across the universe, then applies strategy weights for final total scores. Three strategies: short_term, trend, value.
4. **Single-stock collect** — `services.collect_single()` runs all collectors + scoring for one stock (used when user visits a stock not yet collected today)

### Key Design Patterns

- **Proxy handling**: `base.py` clears proxy env vars at import time and provides `proxy_safe_get()` — use this for all external HTTP calls. Tushare API is accessed directly via the Python client.
- **pywencai responses**: `query_wencai()` in `base.py` handles the fact that pywencai can return either a DataFrame or a dict with a `tableV1` key containing the DataFrame.
- **Wencai multi-row data**: pywencai often returns multiple rows per stock with values scattered across them. `collect_wencai_fields()` in `base.py` merges valid values across all rows.
- **Database**: SQLite at `data/stock_score.db`. `database.py` has automatic column migration (`_migrate_add_columns`). Use `upsert()` for all writes.
- **Stock code format**: Always 6-digit string, zero-padded. Market prefix: `6/5/9` → SH, `0/3` → SZ, `4/8` → BJ.

### Module Map

```
backend/
  main.py              # FastAPI app, lifespan, static file serving
  config.py            # DB path, AI config, schedule times
  database.py          # SQLAlchemy engine, upsert, auto-migration
  engine.py            # ScoreEngine: raw scores → percentile → strategy totals
  services.py          # Business logic: search, industries, collect_single
  scheduler.py         # APScheduler daily collection
  models/              # Stock, DailyData, Score, Strategy ORM models
  collectors/base.py   # proxy_safe_get, query_wencai, collect_wencai_fields
  collectors/*.py      # Individual data collectors
  scorers/*.py         # Per-dimension scoring logic (technical, capital, fundamental, news, heat)
  routers/*.py         # Thin HTTP wrappers calling services.py or collectors
frontend/src/
  api/index.js         # Axios API client
  views/               # Dashboard (tabs: hot/watchlist/industries/search), StockDetail, History
  components/          # ScoreTable, RadarChart, KlineChart, TrendChart
```

### Frontend-Backend Connection

In dev: Vite dev server proxies `/api` → `localhost:8000`. In prod: FastAPI serves `frontend/dist/` as static files with SPA fallback.

### AI Analysis

Optional Zhipu GLM integration (`routers/analysis.py`). Results cached per stock per day in `daily_data` table. Requires `GLM_API_KEY` env var.
