# A股评分系统

本地运行的多维度 A 股评分系统，多数据源采集，SQLite 持久化存储，FastAPI 后端 + Vue 3 前端，集成 AI 智能分析。

## 评分维度

| 维度 | 数据来源 | 指标 |
|---|---|---|
| 技术面 | 腾讯财经 + pandas_ta | MA5/13/30, MACD, RSI(14), KDJ, BOLL, 均线共振, 量比 |
| 资金面 | 东方财富 | 主力净流入, 超大单净流入, 5日主力净流入 |
| 基本面 | pywencai（问财） | PE, PB, ROE, 净利润增速, 市值 |
| 消息面 | pywencai（问财） | 研报数量/评级 |
| 市场热度 | pywencai（问财） | 涨跌幅, 换手率, 量比, 连板数 |

## 评分策略

系统同时计算两个策略维度的总分：

| 策略 | 技术面 | 资金面 | 基本面 | 消息面 | 热度 |
|---|---|---|---|---|---|
| 短线 | 35% | 25% | 0% | 10% | 30% |
| 趋势 | 40% | 30% | 5% | 5% | 20% |
| 价值 | 20% | 15% | 50% | 10% | 5% |

排行榜和详情页同时展示短线、趋势两个总分，无需切换。

## AI 智能分析

集成智谱 GLM 大模型，从五个维度独立评价股票，给出多空判断和操作建议。

- 按日缓存到数据库，同一股票同一天不重复调用
- 详情页自动展示缓存分析，支持手动重新分析
- 分析结果以 Markdown 格式渲染展示

## 技术栈

- **后端**: Python 3.12 + FastAPI + SQLAlchemy + APScheduler
- **前端**: Vue 3 + Vite + Tailwind CSS v4 + ECharts
- **数据库**: SQLite
- **数据源**: 腾讯财经（K线）、东方财富（资金流）、pywencai（基本面/消息/热度）
- **AI**: 智谱 GLM（默认 glm-5.1）
- **包管理**: uv（Python）、npm（Node.js）

## 快速开始

### 环境要求

- [uv](https://docs.astral.sh/uv/) >= 0.11
- Node.js >= 18
- 智谱 API Key（用于 AI 分析，可选）

### 安装

```bash
# 克隆项目
git clone <repo-url> && cd stock-score

# 后端依赖
uv sync

# 前端依赖
cd frontend && npm install && cd ..
```

### 运行

```bash
# 基础启动
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 启用 AI 分析（设置环境变量）
GLM_API_KEY=你的APIKey uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 开发模式（前后端分离）
# 终端 1: 后端
uv run uvicorn backend.main:app --reload --port 8000
# 终端 2: 前端（热更新）
cd frontend && npm run dev
```

访问 http://localhost:8000

### 构建前端

```bash
cd frontend && npm run build
```

构建产物在 `frontend/dist/`，后端自动托管静态文件。

## 项目结构

```
stock_score/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置（数据库、AI、采集时间）
│   ├── database.py          # SQLAlchemy & upsert
│   ├── scheduler.py         # APScheduler 每日16:00自动同步
│   ├── engine.py            # 评分引擎
│   ├── models/              # ORM 模型 (Stock, DailyData, Score, Strategy)
│   ├── collectors/          # 数据采集
│   │   ├── tencent_kline.py # 腾讯财经K线
│   │   ├── technical.py     # 技术指标（pandas_ta）
│   │   ├── capital.py       # 资金流（东方财富）
│   │   ├── fundamental.py   # 基本面（pywencai）
│   │   ├── news.py          # 消息面（pywencai）
│   │   ├── market_heat.py   # 市场热度（pywencai）
│   │   ├── universe.py      # 股票池同步
│   │   └── base.py          # pywencai 封装
│   ├── scorers/             # 评分器（五维度独立评分逻辑）
│   └── routers/             # API 路由
│       ├── scores.py        # 排行榜、详情、K线
│       ├── stocks.py        # 自选股 CRUD
│       ├── trigger.py       # 手动同步
│       └── analysis.py      # AI 分析
├── frontend/
│   └── src/
│       ├── views/           # Dashboard, StockDetail, History
│       ├── components/      # ScoreTable, RadarChart, KlineChart, TrendChart
│       └── api/             # API 客户端
├── data/                    # SQLite 数据库（运行时生成）
└── pyproject.toml           # uv 项目配置
```

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/scores/leaderboard?type=other` | 热门排行榜（含短线/趋势双总分） |
| GET | `/api/scores/leaderboard?type=watchlist` | 自选股排行 |
| GET | `/api/scores/{code}` | 股票详情（双策略评分 + AI缓存） |
| GET | `/api/scores/kline/{code}?days=60` | 日K线数据 |
| GET | `/api/scores/{code}/history` | 历史评分趋势 |
| GET | `/api/analysis/{code}` | AI 分析（有缓存秒回） |
| GET | `/api/stocks/watchlist` | 自选股列表 |
| POST | `/api/stocks/watchlist` | 添加自选股 |
| DELETE | `/api/stocks/watchlist/{code}` | 删除自选股 |
| POST | `/api/trigger/collect` | 手动同步数据 |
| GET | `/api/trigger/status` | 同步状态 |

完整 API 文档: http://localhost:8000/docs

## 股票池

- **自选股**: 用户手动维护
- **指数成分股**: 沪深300、中证500、创业板指
- **热门板块**: 当日涨幅 Top10 板块，每板块取前 5 只

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `GLM_API_KEY` | 空 | 智谱 API Key，不设置则 AI 分析不可用 |
| `AI_BASE_URL` | `https://open.bigmodel.cn/api/coding/paas/v4` | AI API 地址 |
| `AI_MODEL` | `glm-5.1` | 使用的模型 |
