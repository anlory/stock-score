# 港美股支持设计

## 目标

在现有 A 股评分系统中新增港美股（恒生指数、恒生科技、S&P 500、纳斯达克 100）的成分股同步和评分全链路。

## 数据源

- **yfinance**：免费、无需 API key，获取港美股行情和基本面数据
- A 股保持现有 Tushare + pywencai 不变

## 股票代码格式

- `code` 主键保持原始格式，通过 `market` 字段区分市场
- A 股：6 位数字（如 600519），market = SH/SZ/BJ
- 港股：5 位数字（如 00700），market = HK
- 美股：ticker（如 AAPL），market = US

## 改动范围

### 1. Universe 同步

**`collectors/universe.py`** — 新增 `_fetch_hk_us_constituents()`

- 四个指数：S&P 500 (`sp500`)、纳斯达克 100 (`nasdaq100`)、恒生指数 (`hsi`)、恒生科技 (`hstech`)
- yfinance 获取成分股列表和基本信息
- 和现有 A 股 `_fetch_index_constituents()` 并行运行
- 写入 stocks 表，market 设为 HK/US，index_tags 加入对应标签

**yfinance 指数成分股获取方式：**
- S&P 500：`pd.read_html` 从 Wikipedia 获取（最稳定）
- NASDAQ 100：同上，或 yfinance 下载 ETF `QQQ` holdings
- 恒生指数 / 恒生科技：yfinance 下载 ETF `2800.HK` / `3032.HK` holdings，或用 `^HSI` 成分股

### 2. 港美股 Collectors（新建 `collectors/hk_us/`）

#### `collectors/hk_us/technical.py`
- 数据源：`yfinance .history(period="6mo")` 获取 OHLCV
- 用 pandas_ta 计算 MACD、RSI、KDJ、BOLL、MA 等，逻辑复用现有 A 股 technical scorer 的计算方式
- 输出字段与现有 A 股 technical collector 对齐

#### `collectors/hk_us/fundamental.py`
- 数据源：`yfinance .info` 获取 PE、PB、市值、ROE、利润增长率
- 部分字段可能为空（yfinance info 不保证完整），空值写 None
- 输出字段与现有 A 股 fundamental collector 对齐

#### `collectors/hk_us/market_heat.py`
- 数据源：从 yfinance history 计算涨跌幅、换手率（成交量/总股本）
- 量比、连板等 A 股特有指标跳过

#### `collectors/hk_us/news.py`（降级）
- 数据源：`yfinance .news` 获取近期新闻
- 仅做简单新闻数量统计，无研报评分
- 数据不可用时设为 0

#### 不可用维度
- **capital**（主力资金流）：港美股无对应数据，该维度评分设为 0，权重重新分配

### 3. 评分引擎适配

**`engine.py`** — market-aware 评分分发

- `_calc_dimension_scores()` 按 `stock.market` 分组：
  - A 股（SH/SZ/BJ）：走现有 6 维度 scorer
  - 港美股（HK/US）：走港美股 collector + 缩减版 scorer
- 港美股策略权重调整：capital_weight 重分配给 technical 和 fundamental
- percentile 排名在同一 market 内进行（A 股和港美股分开排名）

### 4. 数据库

- `stocks` 表无需 schema 变更（market 字段已是 String，可存 HK/US）
- `daily_data` 表无需 schema 变更（字段通用）
- 缺失维度（capital 相关字段）港美股记录中为 None/0

### 5. 前端

- `/hk` 路由改为复用 Dashboard 组件，通过 market 参数过滤
- 导航栏 "港美股" 入口展示 4 个指数 Tab（恒生指数、恒生科技、S&P 500、纳斯达克 100）
- StockDetail 页面适配不同 market 的代码格式（A 股 6 位、港股 5 位、美股 ticker）
- 搜索支持港美股代码/ticker

### 6. 调度

- `scheduler.py` 和 `trigger.py` 的每日同步任务并行执行 A 股和港美股收集
- 港美股数据量大（~700 只），用 ThreadPoolExecutor 并行获取 yfinance 数据

## 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/collectors/hk_us/__init__.py` | 模块初始化 |
| 新增 | `backend/collectors/hk_us/technical.py` | 港美股技术指标 |
| 新增 | `backend/collectors/hk_us/fundamental.py` | 港美股基本面 |
| 新增 | `backend/collectors/hk_us/market_heat.py` | 港美股市场热度 |
| 新增 | `backend/collectors/hk_us/news.py` | 港美股新闻（降级） |
| 新增 | `backend/collectors/hk_us/universe.py` | 港美股成分股同步 |
| 修改 | `backend/collectors/universe.py` | 调用港美股同步 |
| 修改 | `backend/engine.py` | market-aware 评分分发 |
| 修改 | `backend/services.py` | 港美股搜索/详情适配 |
| 修改 | `backend/trigger.py` | 触发港美股收集 |
| 修改 | `frontend/src/views/Dashboard.vue` | 港美股 Dashboard |
| 修改 | `frontend/src/views/StockDetail.vue` | 多市场代码适配 |
| 修改 | `frontend/src/router/index.js` | 港美股路由 |
| 修改 | `pyproject.toml` | 添加 yfinance 依赖 |
