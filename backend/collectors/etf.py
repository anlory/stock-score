"""ETF universe sync and data collection.

Uses Tushare fund_daily (same schema as stock daily) for K-line data.
ETFs are scored with technical + heat dimensions only (no capital flow / fundamental / news).
"""
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

import pandas as pd
import pandas_ta as ta

from backend.collectors.tushare_client import get_pro, to_ts_code, to_ts_date, ts_call
from backend.database import upsert
from backend.models import DailyData, Stock

logger = logging.getLogger(__name__)
_MAX_WORKERS = 10

# ── Curated popular ETF list (~100) ────────────────────
# Categories: 宽基 / 行业 / 跨境
POPULAR_ETFS: dict[str, dict] = {
    # ── 宽基 ────────────────────────────────
    "510050": {"name": "上证50ETF",    "cat": "宽基"},
    "510300": {"name": "沪深300ETF",   "cat": "宽基"},
    "510500": {"name": "中证500ETF",   "cat": "宽基"},
    "512100": {"name": "中证1000ETF",  "cat": "宽基"},
    "159915": {"name": "创业板ETF",    "cat": "宽基"},
    "159919": {"name": "沪深300ETF",   "cat": "宽基"},
    "588000": {"name": "科创50ETF",    "cat": "宽基"},
    "510880": {"name": "红利ETF",      "cat": "宽基"},
    "159949": {"name": "创业板50ETF",  "cat": "宽基"},
    "512980": {"name": "传媒ETF",      "cat": "宽基"},
    "510210": {"name": "上证指数ETF",  "cat": "宽基"},
    "511010": {"name": "国债ETF",      "cat": "宽基"},
    "511260": {"name": "十年国债ETF",  "cat": "宽基"},
    "512010": {"name": "医药ETF",      "cat": "宽基"},
    "159901": {"name": "深证100ETF",   "cat": "宽基"},
    "159922": {"name": "中证500ETF",   "cat": "宽基"},
    "588050": {"name": "科创50ETF",    "cat": "宽基"},
    "562500": {"name": "中证A500ETF",  "cat": "宽基"},
    "159338": {"name": "中证A500ETF",  "cat": "宽基"},
    "159981": {"name": "能源化工ETF",  "cat": "宽基"},
    "512660": {"name": "军工ETF",      "cat": "宽基"},
    "512100": {"name": "中证1000ETF",  "cat": "宽基"},
    "159967": {"name": "创成长ETF",    "cat": "宽基"},
    "512560": {"name": "中证军工ETF",  "cat": "宽基"},
    # ── 行业 ────────────────────────────────
    "512880": {"name": "证券ETF",      "cat": "行业"},
    "512000": {"name": "券商ETF",      "cat": "行业"},
    "512690": {"name": "酒ETF",        "cat": "行业"},
    "159996": {"name": "芯片ETF",      "cat": "行业"},
    "512480": {"name": "半导体ETF",    "cat": "行业"},
    "515030": {"name": "新能源车ETF",  "cat": "行业"},
    "515790": {"name": "光伏ETF",      "cat": "行业"},
    "516160": {"name": "新能源ETF",    "cat": "行业"},
    "512170": {"name": "医疗ETF",      "cat": "行业"},
    "512010": {"name": "医药ETF",      "cat": "行业"},
    "159881": {"name": "科创芯片ETF",  "cat": "行业"},
    "516150": {"name": "稀土ETF",      "cat": "行业"},
    "512200": {"name": "房地产ETF",    "cat": "行业"},
    "512070": {"name": "非银ETF",      "cat": "行业"},
    "515050": {"name": "5GETF",        "cat": "行业"},
    "515880": {"name": "通信ETF",      "cat": "行业"},
    "512720": {"name": "计算机ETF",    "cat": "行业"},
    "159825": {"name": "农业ETF",      "cat": "行业"},
    "512400": {"name": "有色金属ETF",  "cat": "行业"},
    "159992": {"name": "创新药ETF",    "cat": "行业"},
    "516950": {"name": "基建ETF",      "cat": "行业"},
    "512710": {"name": "军工龙头ETF",  "cat": "行业"},
    "159766": {"name": "旅游ETF",      "cat": "行业"},
    "515170": {"name": "食品饮料ETF",  "cat": "行业"},
    "512970": {"name": "云计算ETF",    "cat": "行业"},
    "562500": {"name": "中证A500ETF",  "cat": "行业"},
    "588200": {"name": "科创板ETF",    "cat": "行业"},
    "513050": {"name": "中概互联ETF",  "cat": "行业"},
    "164906": {"name": "互联网ETF",    "cat": "行业"},
    "159605": {"name": "中概互联网ETF","cat": "行业"},
    "512360": {"name": "新材料ETF",    "cat": "行业"},
    "516110": {"name": "汽车ETF",      "cat": "行业"},
    "159869": {"name": "游戏ETF",      "cat": "行业"},
    "515250": {"name": "智能汽车ETF",  "cat": "行业"},
    "512800": {"name": "银行ETF",      "cat": "行业"},
    "159920": {"name": "恒生ETF",      "cat": "行业"},
    "512010": {"name": "医药ETF",      "cat": "行业"},
    "159883": {"name": "医疗器械ETF",  "cat": "行业"},
    "560260": {"name": "数字经济ETF",  "cat": "行业"},
    "159632": {"name": "人工智能ETF",  "cat": "行业"},
    "515000": {"name": "科技ETF",      "cat": "行业"},
    "512760": {"name": "芯片龙头ETF",  "cat": "行业"},
    "159801": {"name": "芯片产业ETF",  "cat": "行业"},
    "516510": {"name": "新能源汽车ETF","cat": "行业"},
    "512610": {"name": "军工ETF",      "cat": "行业"},
    "512680": {"name": "半导体ETF",    "cat": "行业"},
    "510410": {"name": "资源ETF",      "cat": "行业"},
    # ── 跨境 ────────────────────────────────
    "513100": {"name": "纳指100ETF",   "cat": "跨境"},
    "513500": {"name": "标普500ETF",   "cat": "跨境"},
    "513060": {"name": "恒生科技ETF",  "cat": "跨境"},
    "159920": {"name": "恒生ETF",      "cat": "跨境"},
    "513030": {"name": "德国DAX ETF",  "cat": "跨境"},
    "513080": {"name": "法国CAC ETF",  "cat": "跨境"},
    "513000": {"name": "日经225 ETF",  "cat": "跨境"},
    "513520": {"name": "日经ETF",      "cat": "跨境"},
    "159560": {"name": "标普500 ETF",  "cat": "跨境"},
    "513050": {"name": "中概互联ETF",  "cat": "跨境"},
    "159605": {"name": "中概互联网ETF","cat": "跨境"},
    "513550": {"name": "标普信息科技ETF","cat": "跨境"},
    "513180": {"name": "恒生科技ETF",  "cat": "跨境"},
    "159509": {"name": "纳指科技ETF",  "cat": "跨境"},
    "513060": {"name": "恒生科技ETF",  "cat": "跨境"},
    "513660": {"name": "恒生医疗ETF",  "cat": "跨境"},
}

# Category → display label
ETF_CATEGORIES = {
    "宽基": "宽基ETF",
    "行业": "行业ETF",
    "跨境": "跨境ETF",
}


def _get_exchange(code: str) -> str:
    """Get exchange suffix for ETF code."""
    if code.startswith("5"):
        return "SH"
    return "SZ"


def sync_etf_universe(session) -> int:
    """Sync curated popular ETFs into stocks table with market='ETF'.
    Returns count of ETFs synced."""
    synced = 0
    for code, info in POPULAR_ETFS.items():
        upsert(session, Stock, {
            "code": code,
            "name": info["name"],
            "market": "ETF",
            "industry": info["cat"],
            "is_watchlist": False,
            "index_tags": json.dumps([info["cat"]]),
        }, ["code"])
        synced += 1
    session.commit()
    logger.info(f"ETF universe synced: {synced} ETFs")
    return synced


def _compute_returns(closes: list[float]) -> dict:
    """Compute multi-period returns from close prices."""
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
    """Detect chart patterns from indicator values."""
    tags = []
    ma5 = _f(last_row, "SMA_5");  ma13 = _f(last_row, "SMA_13")
    pma5 = _f(prev_row, "SMA_5");  pma13 = _f(prev_row, "SMA_13")
    if None not in (ma5, ma13, pma5, pma13):
        if ma5 > ma13 and pma5 < pma13:
            tags.append("MA5上穿MA13")
        elif ma5 < ma13 and pma5 > pma13:
            tags.append("MA5下穿MA13")
    vr = _f(last_row, "VOL_RATIO")
    if vr is not None and change_pct is not None and vr > 2 and change_pct > 3:
        tags.append("放量上攻")
    dif = _f(last_row, "MACD_12_26_9");  dea = _f(last_row, "MACDs_12_26_9")
    pdif = _f(prev_row, "MACD_12_26_9");  pdea = _f(prev_row, "MACDs_12_26_9")
    if None not in (dif, dea, pdif, pdea):
        if dif > dea and pdif <= pdea:
            tags.append("MACD金叉")
    return tags


def _f(row, col):
    """Safely extract and round a float from a DataFrame row."""
    val = row.get(col)
    try:
        return round(float(val), 4) if pd.notna(val) else None
    except (TypeError, ValueError):
        return None


def _process_one_etf(code: str, today: str) -> dict | None:
    """Fetch fund_daily for one ETF and compute technical indicators."""
    try:
        pro = get_pro()
        start = to_ts_date((date.fromisoformat(today) - timedelta(days=130)).isoformat())
        # Use fund_daily instead of daily
        ts_c = to_ts_code(code)
        df = ts_call(pro.fund_daily, ts_code=ts_c, start_date=start, end_date=to_ts_date(today))
        if df is None or len(df) < 15:
            return None

        df = df.sort_values("trade_date").reset_index(drop=True)
        df = df.rename(columns={"vol": "volume"})

        # Same pandas_ta indicators as stock technical
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
        logger.error(f"ETF technical failed for {code}: {e}")
        return None


def collect_etf_technical(session, target_codes: set[str] = None, today: str = None) -> int:
    """Collect technical data for ETFs using fund_daily API."""
    today = today or date.today().isoformat()
    codes = sorted(target_codes) if target_codes else []
    if not codes:
        logger.warning("No target codes for ETF technical collection")
        return 0

    results = []
    done = 0
    total = len(codes)
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_process_one_etf, code, today): code for code in codes}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
            done += 1
            if done % 20 == 0 or done == total:
                logger.info(f"ETF Technical: {done}/{total}")

    count = 0
    for record in results:
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"ETF upsert failed for {record.get('code')}: {e}")

    session.commit()
    logger.info(f"ETF technical data collected: {count} ETFs")
    return count
