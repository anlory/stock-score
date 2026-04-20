# 个股详情页信息增强 Design

## 背景

当前 `frontend/src/views/StockDetail.vue` 只显示：名称/代码、双策略分数、AI 分析文本、雷达图 + 五维评分、原始指标表、TradingView K 线。用户希望扩充为「像样的个股报告」——含公司介绍、强关联板块、最近趋势、AI 综合总结。

后端数据目前仅覆盖评分所需指标（`DailyData`），没有公司资料、板块涨跌、近期涨跌幅、形态标签等字段。需要扩展数据采集、数据库、API 和前端。

## 目标

在个股详情页新增三张信息卡片（公司概况 / 板块关联 / 近期趋势），并把 AI 分析升级为结构化的四段研判，数据来自本地采集 + AI，采用「静态信息懒加载 + 动态信息随每日任务」的分层缓存策略。

## 非目标

- 不新增实时行情推送
- 不做历史板块表现的独立页面（仅嵌入详情页）
- 不扩充形态识别库（首期只上 3-4 条最常用规则）
- 不新增前端测试基建（手工验收）

## 数据库扩展

### `Stock` 表新增字段（静态资料，懒加载）

| 字段 | 类型 | 含义 |
|---|---|---|
| `business` | Text | 主营业务简介 |
| `industry` | String | 所属行业 |
| `concepts` | Text (JSON string) | 概念板块列表，如 `["AI芯片","华为概念"]` |
| `total_share` | Float | 总股本（亿股） |
| `float_share` | Float | 流通股本（亿股） |
| `list_date` | String | 上市日期（YYYY-MM-DD） |
| `profile_updated_at` | DateTime | 资料抓取时间 |

### `DailyData` 表新增字段（动态数据，随每日任务）

| 字段 | 类型 | 含义 |
|---|---|---|
| `return_5d` | Float | 近 5 日涨跌幅 % |
| `return_20d` | Float | 近 20 日涨跌幅 % |
| `return_60d` | Float | 近 60 日涨跌幅 % |
| `industry_change` | Float | 所属行业今日涨跌幅 % |
| `industry_change_5d` | Float | 行业近 5 日涨跌幅 % |
| `industry_change_20d` | Float | 行业近 20 日涨跌幅 % |
| `pattern_tags` | Text (JSON string) | 形态标签列表 |

### 迁移

SQLAlchemy `create_all` 只处理不存在的表，对已存在表的新列无效。在 `backend/database.py` 启动时运行一次性迁移函数：对每个新字段 `PRAGMA table_info` 判断是否存在，不存在则 `ALTER TABLE ... ADD COLUMN ...`。SQLite 原生支持 `ADD COLUMN`。

## 采集器

### `backend/collectors/profile.py`（懒加载，首次访问触发）

入口：`fetch_profile(session, code) -> Stock`

- 若 `stock.profile_updated_at` 在 30 天内，直接返回现有 `Stock` 记录
- 否则调用 akshare：
  - `stock_individual_info_em(code)` → 行业、总股本、流通股本、上市日期
  - `stock_zyjs_ths(code)` → 主营业务（取前 200 字）
  - 概念板块：用 pywencai `"{name} 所属概念"` 或 akshare `stock_board_concept_name_ths` 反查；优先 pywencai，失败降级为空列表
- 把结果 `upsert` 到 `Stock`，`profile_updated_at` 置为当前时间
- 任何字段抓取失败 → 不覆盖已有值、不抛出异常（记日志）

### `backend/collectors/trend.py`（随每日任务）

入口：`collect_trend(session, target_codes: set[str])`

- 对每个 code：
  - 从 tencent_kline 取近 65 交易日收盘价，计算 `return_5d / 20d / 60d`
  - 读 `Stock.industry`，用 `akshare.stock_board_industry_hist_em` 拿行业近 1/5/20 日涨跌
  - 形态标签规则（首期只上这 4 条，后续可扩）：
    - `ma5 上穿 ma13`：`ma5 > ma13 且 prev_ma5 < prev_ma13`
    - `ma5 下穿 ma13`：`ma5 < ma13 且 prev_ma5 > prev_ma13`
    - `放量上攻`：`volume_ratio > 2 且 change_pct > 3`
    - `MACD 金叉`：`macd_dif > macd_dea 且前一日 macd_dif < macd_dea`（需从历史 DailyData 读前一日 dif/dea；若无数据则跳过）
  - `upsert` 到 `DailyData`

接入：`backend/engine.py` 的每日采集流程，在 `collect_technical` 之后调用。允许单独执行（便于补算历史）。

## API

### 新增 `GET /api/stocks/{code}/profile`

路由：`backend/routers/stocks.py`

- 调 `fetch_profile` 懒加载
- 返回：
  ```json
  {
    "code": "000001",
    "name": "平安银行",
    "business": "...",
    "industry": "银行",
    "concepts": ["金融改革","大金融"],
    "total_share": 194.06,
    "float_share": 194.05,
    "list_date": "1991-04-03"
  }
  ```

### 扩展 `GET /api/scores/{code}`

路由：`backend/routers/scores.py::get_stock_detail`

- 返回体新增 `trend_info` 字段（避免与现有 `trend` 策略分数冲突）：
  ```json
  "trend_info": {
    "return_5d": 3.2, "return_20d": -1.1, "return_60d": 12.5,
    "industry_change": 0.8, "industry_change_5d": 2.1, "industry_change_20d": -0.5,
    "pattern_tags": ["MA5上穿MA13","放量上攻"]
  }
  ```

### 修改 `GET /api/analysis/{code}`

路由：`backend/routers/analysis.py::analyze_stock`

- `_build_prompt` 新增入参：公司简介、行业、概念、近期涨跌、行业对比、形态标签
- 输出要求改为 4 段 markdown：
  1. **公司概况**：一句话概括业务 + 所处行业地位
  2. **板块关联**：所属核心板块 + 板块近期表现对个股的影响
  3. **近期走势**：5/20/60 日涨跌 + 形态信号的综合判断
  4. **综合研判**：多空判断 + 短线 / 趋势操作建议
- 字数上限从 300 放宽到 600
- 缓存沿用 `daily_data.ai_analysis`，无需加字段

## 前端

### `frontend/src/api/index.js`

新增：
```js
export const getStockProfile = (code) =>
  api.get(`/stocks/${code}/profile`).then(r => r.data)
```

### `frontend/src/views/StockDetail.vue` 布局

从上到下：

1. 返回按钮 **（保留）**
2. 名称 + 代码 + 双策略分数徽章 **（保留）**
3. **【公司概况卡】（新增）**
   - 行业 chip · 概念 chip（多个，`bg-gray-800 text-xs px-2 py-0.5 rounded`）
   - 主营业务：默认显示 2 行，溢出时「展开/收起」切换
   - 底部：上市日期 · 总股本 · 流通股本（小字灰）
4. **【板块关联卡】（新增）**
   - 所属行业名 + 今日 / 5 日 / 20 日涨跌（涨红跌绿）
5. **【近期趋势卡】（新增）**
   - 近 5 / 20 / 60 日涨跌幅（涨红跌绿）
   - 形态标签 chip 列表
6. **【AI 综合研判】（改造）**
   - 4 段 markdown；markdown `##` 渲染为小标题
7. 雷达图 + 五维评分 **（保留）**
8. K 线图 **（保留）**
9. 原始指标 **（改造）**：默认折叠，标题行加「展开」按钮

### 加载行为

- `load()` 并行 `getStockDetail(code)` + `getStockProfile(code)`
- 公司简介、板块、近期趋势拿到就渲染
- AI 分析块保持「点击才生成」；若后端返回 `ai_analysis` 缓存命中则直接渲染
- 骨架屏覆盖新卡片（沿用现有 `animate-pulse` 样式）
- 任一接口失败：该卡片显示「暂无数据」，不影响其他区块

### 视觉规范

- 卡片：`bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4`
- chip：`bg-gray-800 text-xs px-2 py-0.5 rounded text-gray-300`
- 涨：`text-red-400`；跌：`text-green-400`（A 股习惯）
- 标题：`text-sm text-gray-400 font-semibold mb-3`

## 测试策略

### 后端（pytest）

- `collectors/profile.py`
  - mock akshare，断言 Stock 表新字段被正确写入
  - 30 天内命中缓存不调用 akshare
  - akshare 抛异常时不覆盖已有值、不抛到调用方
- `collectors/trend.py`
  - 给定 mock 的 DailyData 历史和 tencent_kline 序列，断言 `return_N` 正确
  - 形态标签四条规则各一个用例
- `routers/analysis.py::_build_prompt`
  - 断言生成的 prompt 包含公司简介、所属行业、近期涨跌、形态标签文案

### 前端

手工验收：
1. 打开有完整数据的股票，三张卡片正常渲染
2. 打开无资料（新股或采集失败）的股票，卡片显示「暂无」而非崩溃
3. 点「开始分析」，AI 输出 4 段 markdown 结构
4. 原始指标默认折叠，点击展开

## 实施顺序

每一步可独立合入、独立验证：

1. **DB Schema 扩展 + 启动时迁移**
2. **Profile 采集器 + `/api/stocks/{code}/profile`**
3. **Trend 采集器 + 扩展 `/api/scores/{code}`**
4. **AI Prompt 改造**
5. **前端 StockDetail.vue 新卡片 + 并行加载**

## 风险与缓解

- **akshare 偶发空返回**：采集器容错，不覆盖已有值
- **pywencai 概念反查不稳**：降级为空列表；用户仍能看到行业 + 公司简介
- **形态标签易扩散**：首期只上 4 条；其余规则写 TODO 注释
- **SQLite ALTER TABLE 限制**：仅 `ADD COLUMN` 可用，不支持改列类型；本设计只新增列，符合限制
- **AI 输出变长到 600 字**：前端 markdown 样式已支持滚动；移动端建议后续加折叠（非本期范围）
