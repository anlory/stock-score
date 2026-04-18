# A股评分系统

本地运行的多维度 A 股评分系统，通过 pywencai（问财）采集数据，SQLite 持久化存储，FastAPI 提供 API，Vue 3 前端展示。

## 评分维度

| 维度 | 数据来源 | 指标 |
|---|---|---|
| 技术面 | pywencai | MA5/13/30, MACD, RSI(14), KDJ, BOLL, 量比 |
| 资金面 | pywencai | 主力净流入, 超大单, 北向资金, 融资净买入 |
| 基本面 | pywencai | PE, PB, ROE, 净利润增速, 市值 |
| 消息面 | pywencai | 研报数量/评级, 公告类型, 舆情情感 |
| 市场热度 | pywencai | 涨跌幅, 换手率, 量比, 连板数, 板块排名 |

## 预设策略

| 策略 | 技术面 | 资金面 | 基本面 | 消息面 | 热度 |
|---|---|---|---|---|---|
| 短线 | 35% | 25% | 0% | 10% | 30% |
| 趋势 | 40% | 30% | 5% | 5% | 20% |
| 价值 | 20% | 15% | 50% | 10% | 5% |

## 技术栈

- **后端**: Python 3.12 + FastAPI + SQLAlchemy + APScheduler
- **前端**: Vue 3 + Vite + Tailwind CSS + ECharts
- **数据库**: SQLite
- **数据源**: pywencai（同花顺问财）

## 快速开始

### 环境要求

- [uv](https://docs.astral.sh/uv/) >= 0.11
- Node.js >= 18

### 安装

```bash
# 克隆项目
git clone <repo-url> && cd stock-score

# 后端依赖
uv venv --python 3.12
uv pip install -e .

# 前端依赖
cd frontend && npm install && cd ..
```

### 运行

```bash
# 启动后端（同时服务前端静态文件）
uv run uvicorn backend.main:app --port 8000

# 或开发模式（前后端分离）
# 终端 1: 后端
uv run uvicorn backend.main:app --reload --port 8000
# 终端 2: 前端（热更新）
cd frontend && npm run dev
```

访问 http://localhost:8000

### 测试

```bash
uv run pytest tests/ -v
```

## 项目结构

```
stock_score/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置
│   ├── database.py          # SQLAlchemy & upsert
│   ├── scheduler.py         # APScheduler 每日采集
│   ├── engine.py            # 评分引擎
│   ├── models/              # ORM 模型 (Stock, DailyData, Score, Strategy)
│   ├── collectors/          # 数据采集 (technical, capital, fundamental, news, heat)
│   ├── scorers/             # 评分器 (五维度独立评分逻辑)
│   └── routers/             # API 路由 (stocks, scores, trigger)
├── frontend/
│   └── src/
│       ├── views/           # Dashboard, StockDetail, History
│       ├── components/      # ScoreTable, RadarChart, TrendChart
│       └── api/             # API 客户端
├── data/                    # SQLite 数据库（运行时生成）
└── tests/                   # pytest 测试
```

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/scores/leaderboard` | 排行榜 (strategy, type=watchlist/other) |
| GET | `/api/scores/{code}` | 股票评分详情 |
| GET | `/api/scores/{code}/history` | 历史评分趋势 |
| GET | `/api/stocks/watchlist` | 自选股列表 |
| POST | `/api/stocks/watchlist` | 添加自选股 |
| DELETE | `/api/stocks/watchlist/{code}` | 删除自选股 |
| POST | `/api/trigger/collect` | 手动触发采集 |
| GET | `/api/trigger/status` | 采集状态 |

完整 API 文档: http://localhost:8000/docs

## 股票池

- **自选股**: 用户手动维护
- **指数成分股**: 沪深300、中证500、创业板指
- **热门板块**: 当日涨幅 Top10 板块，每板块取前 5 只
