# backend/collectors/technical.py
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

import pandas as pd
import pandas_ta as ta

from backend.collectors.tushare_client import get_pro, to_ts_code, to_ts_date, ts_call
from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)
_MAX_WORKERS = 10


def _compute_returns(closes: list[float]) -> dict:
    out = {"return_5d": None, "return_20d": None, "return_60d": None,
           "return_3d": None, "return_13d": None, "return_mid": None}
    today_c = closes[-1] if closes else None
    for window, key in [(3, "return_3d"), (5, "return_5d"), (13, "return_13d"),
                        (20, "return_20d"), (60, "return_60d")]:
        if today_c and len(closes) > window and closes[-window - 1]:
            out[key] = round((today_c - closes[-window - 1]) / closes[-window - 1] * 100, 2)
    # return_mid: 25-day return (day[-31] → day[-6]), excluding last 5 days
    if len(closes) > 31 and closes[-31] and closes[-6]:
        out["return_mid"] = round((closes[-6] - closes[-31]) / closes[-31] * 100, 2)
    return out


def _detect_patterns(last_row, prev_row, change_pct) -> list[str]:
    tags = []
    ma5   = _f(last_row, "SMA_5");  ma13  = _f(last_row, "SMA_13")
    pma5  = _f(prev_row, "SMA_5");  pma13 = _f(prev_row, "SMA_13")
    if None not in (ma5, ma13, pma5, pma13):
        if ma5 > ma13 and pma5 < pma13:
            tags.append("MA5上穿MA13")
        elif ma5 < ma13 and pma5 > pma13:
            tags.append("MA5下穿MA13")
    vr = _f(last_row, "VOL_RATIO")
    if vr is not None and change_pct is not None and vr > 2 and change_pct > 3:
        tags.append("放量上攻")
    dif  = _f(last_row, "MACD_12_26_9");  dea  = _f(last_row, "MACDs_12_26_9")
    pdif = _f(prev_row, "MACD_12_26_9");  pdea = _f(prev_row, "MACDs_12_26_9")
    if None not in (dif, dea, pdif, pdea):
        if dif > dea and pdif <= pdea:
            tags.append("MACD金叉")
    return tags


def _process_one(code: str, today: str) -> dict | None:
    try:
        pro = get_pro()
        start = to_ts_date((date.fromisoformat(today) - timedelta(days=130)).isoformat())
        df = ts_call(pro.daily, ts_code=to_ts_code(code), start_date=start, end_date=to_ts_date(today))
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

        closes = df["close"].astype(float).tolist()
        volumes = df["volume"].astype(float).tolist()
        change_pct = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2) if len(closes) >= 2 and closes[-2] else None
        returns = _compute_returns(closes)
        tags = _detect_patterns(last, prev, change_pct)

        # Volume averages
        vol_ma3 = sum(volumes[-3:]) / 3 if len(volumes) >= 3 else None
        vol_ma5 = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else None
        vol_ma13 = sum(volumes[-13:]) / 13 if len(volumes) >= 13 else None
        vol_ma30 = sum(volumes[-30:]) / 30 if len(volumes) >= 30 else None

        # 30-day and 10-day new high
        close_today = closes[-1]
        is_30d_high = 1 if close_today >= max(closes[-30:]) and len(closes) >= 30 else 0
        is_10d_high = 1 if close_today >= max(closes[-10:]) and len(closes) >= 10 else 0

        # MA5 3-day slope: (MA5[-1] - MA5[-4]) / MA5[-4]
        ma5_vals = [df.iloc[i].get("SMA_5") for i in range(-4, 0)]
        ma5_slope3 = None
        if all(pd.notna(v) for v in ma5_vals) and ma5_vals[0] and ma5_vals[0] > 0:
            ma5_slope3 = round((float(ma5_vals[3]) - float(ma5_vals[0])) / float(ma5_vals[0]) * 100, 4)

        # Channel B: count of last 5 days where close >= MA5
        close_above_ma5_5d = 0
        for i in range(-5, 0):
            c = closes[i]
            m = _f(df.iloc[i], "SMA_5")
            if m is not None and c >= m:
                close_above_ma5_5d += 1

        # Channel A: latest close above MA5
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
        logger.error(f"Technical failed for {code}: {e}")
        return None


def collect_technical(session, target_codes: set[str] = None, today: str = None) -> int:
    today = today or date.today().isoformat()
    codes = sorted(target_codes) if target_codes else []
    if not codes:
        logger.warning("No target codes for technical collection")
        return 0

    results = []
    done = 0
    total = len(codes)
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_process_one, code, today): code for code in codes}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
            done += 1
            if done % 50 == 0 or done == total:
                logger.info(f"Technical: {done}/{total}")

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
