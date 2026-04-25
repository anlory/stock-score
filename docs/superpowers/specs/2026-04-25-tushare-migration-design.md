# Tushare 数据源迁移设计

**日期**：2026-04-25  
**范围**：将除 `news.py` 外的所有数据 collector 从 pywencai / 腾讯K线 / akshare / 东方财富 迁移至 tushare。

---

## 背景

当前数据源存在以下问题：
- `pywencai`：非官方库，接口不稳定，返回格式随查询变化
- 腾讯K线（`qt.gtimg.cn`）：非官方接口，无保障
- akshare 行业历史：依赖东方财富接口，受代理影响
- 东方财富资金流向：非官方 API

tushare 是正规金融数据平台，提供稳定的接口和统一的数据格式。用户已有 token，通过 `jiaoch.site` 代理访问。

---

## 不迁移的部分

- `news.py`：保持 pywencai（研报数量/评级在 tushare 免费层不稳定）

---

## 一、共享基础设施

### `collectors/tushare_client.py`（新文件）

单例 pro 实例，全局共享：

```python
import tushare as ts
from backend.config import TUSHARE_TOKEN, TUSHARE_URL

_pro = None

def get_pro():
    global _pro
    if _pro is None:
        _pro = ts.pro_api(TUSHARE_TOKEN)
        _pro._DataApi__token = TUSHARE_TOKEN
        _pro._DataApi__http_url = TUSHARE_URL
    return _pro
```

格式转换工具（同文件）：

```python
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

### `config.py` 新增

```python
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
TUSHARE_URL = os.getenv("TUSHARE_URL", "http://jiaoch.site")
```

启动命令新增环境变量：
```bash
TUSHARE_TOKEN=xxx uv run uvicorn backend.main:app ...
```

---

## 二、批量日线 Collectors

这四个 collector 按 `trade_date` 全量拉取，过滤出 `target_codes` 后 upsert。

### `technical.py`

- 历史K线：`pro.daily(ts_code=code, start_date=90天前, end_date=today)` 并发拉取（ThreadPoolExecutor，10 workers）
- 返回字段：`open, high, low, close, vol, amount`
- pandas_ta 指标计算逻辑不变（SMA5/13/30、MACD、RSI、KDJ、BOLL）
- 去掉对 `tencent_kline.py` 的依赖

### `fundamental.py`

两个接口合并写入同一条 `DailyData`：

| 字段 | 接口 | tushare 字段 |
|------|------|-------------|
| pe | `daily_basic(trade_date)` | `pe_ttm` |
| pb | `daily_basic(trade_date)` | `pb` |
| market_cap | `daily_basic(trade_date)` | `total_mv`（万元→亿元） |
| roe | `fina_indicator(ts_code, period)` | `roe` |
| profit_growth_yoy | `fina_indicator(ts_code, period)` | `netprofit_yoy` |

`period`：自动计算最近已公布财报期（当前月 ≤ 4 则取上上年年报，5-8 取上年年报，9-10 取当年中报，11+ 取当年三季报）。

`daily_basic` 一次拉全市场，`fina_indicator` 按股分批（每次最多 50 支）。

### `market_heat.py`

| 字段 | 接口 | tushare 字段 |
|------|------|-------------|
| change_pct | `daily(trade_date)` | `pct_chg` |
| turnover_rate | `daily_basic(trade_date)` | `turnover_rate` |
| volume_ratio | `daily_basic(trade_date)` | `volume_ratio` |
| consecutive_limit_up | `limit_list_d` 近10日 | 逐日统计连续天数 |

`daily` 和 `daily_basic` 各拉一次全市场，按 ts_code join 后过滤 `target_codes`。  
`limit_list_d` 不含连续天数字段，改为：查询最近 10 个交易日的涨停列表，对 `target_codes` 中的每只股票统计从今日往前连续出现的天数，不在今日涨停列表中的设为 0。10 个交易日一次性批量查（循环 10 次调用，每次一天），结果 join 合并。

### `capital.py`

- `pro.moneyflow(trade_date=today)` 全市场一次拉取
- `buy_lg_amount` + `buy_elg_amount` → `main_inflow_today`（大单+超大单买入额，万元）
- `net_mf_amount` → 净流入
- 5日累计：`pro.moneyflow(ts_code=code, start_date=10天前, end_date=today)` 取最近 5 个有数据的交易日，对 `net_mf_amount` 求和 → `main_inflow_5d`（逐股查询，并发执行）

---

## 三、Universe 同步

### `universe.py`

**指数成分股**：

| 指数 | 代码 | tag |
|------|------|-----|
| 沪深300 | `000300.SH` | hs300 |
| 中证500 | `000905.SH` | zz500 |
| 创业板指 | `399006.SZ` | cyb |

调用 `pro.index_member(index_code=..., fields='ts_code,stk_code,stk_name')`。

**股票基础信息**：`pro.stock_basic(exchange='', list_status='L', fields='ts_code,name,industry,market')` 全量拉取，写入 `Stock.name` 和 `Stock.industry`（避免 profile 阶段重复查询）。

**热门板块股票**（替换 pywencai 逻辑）：

1. `pro.ths_index(exchange='A', type='N')` → 拿全部同花顺行业指数（约 100 个），取 `ts_code` 和 `name`
2. `pro.ths_daily(trade_date=today)` → 拿今日所有行业涨跌幅，取涨幅最大 10 个
3. 对每个行业：`pro.ths_member(ts_code=行业代码)` → 拿成分股，取前 5 只
4. 写入 `Stock` 表（如不存在则新建）

同时将 `行业名 → THS指数代码` 的映射存入 `tushare_client.py` 中的模块级 dict `INDUSTRY_TS_CODE_MAP`，`universe.py` 负责填充，`trend.py` 直接 import 使用。

---

## 四、Profile

### `profile.py`

缓存策略不变（30天 TTL），数据源替换：

| 字段 | 原来 | 替换为 |
|------|------|--------|
| total_share / float_share | 腾讯API推算 | `stock_basic.total_share / float_share`（万股→亿股） |
| total_mv / float_mv | 腾讯API | `daily_basic.total_mv / circ_mv`（万元→亿元） |
| pe / pb | 腾讯API | `daily_basic.pe_ttm / pb` |
| industry | pywencai | `stock_basic.industry`（universe 同步时已写入） |
| business | pywencai "经营范围" | `pro.stock_company(ts_code=code, fields='business_scope')` |
| concepts | pywencai | 全量反向映射缓存（见下） |

**概念板块缓存**：
- 首次调用时：`pro.concept()` 拿全部概念列表 → 对每个概念调用 `pro.concept_detail()` 拿成分股 → 构建 `{ts_code: [概念名列表]}` 反向映射
- 缓存存在内存中（模块级 dict），进程重启后重建，有效期无需持久化
- 构建时机：profile 第一次被调用时懒加载，后台单线程构建（不阻塞主请求）

---

## 五、Trend

### `trend.py`

**K线收益率**（替换腾讯K线）：

- `pro.daily(ts_code=code, start_date=65天前, end_date=today)` → 取 `close` 列
- 计算 5/20/60 日收益率逻辑不变

**行业涨跌**（替换 akshare）：

- 从 `Stock.industry` 获取行业名 → 查 `tushare_client.INDUSTRY_TS_CODE_MAP`（universe 同步时填充）映射到 THS 指数 ts_code
- `pro.ths_daily(ts_code=行业指数代码, start_date=25天前, end_date=today)` → 取最近 25 个交易日收盘价
- 计算 1日/5日/20日行业涨跌幅（首尾差值）

`_IndustryCache` 线程安全缓存逻辑不变，只替换内部的 `_fetch_industry_changes` 实现。

**pattern tags 检测不变**（MA金叉、放量上攻、MACD金叉）。

---

## 依赖变更

```toml
# 移除
pywencai  # 仅 news.py 保留，其余不需要
akshare

# 新增
tushare
```

腾讯K线相关文件 `collectors/tencent_kline.py` 可在迁移完成后删除。

---

## 启动方式变更

```bash
# 开发
TUSHARE_TOKEN=xxx uv run uvicorn backend.main:app --reload --port 8000

# 生产
TUSHARE_TOKEN=xxx TUSHARE_URL=http://jiaoch.site uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

---

## 迁移顺序

1. 基础设施：`tushare_client.py` + `config.py`
2. 批量日线：`technical` → `fundamental` → `market_heat` → `capital`
3. `universe.py`（包含热门板块 + industry 映射）
4. `profile.py`（概念缓存）
5. `trend.py`（行业涨跌替换）
6. 清理：删除 `tencent_kline.py`，更新 `pyproject.toml`
