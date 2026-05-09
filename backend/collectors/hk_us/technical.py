# backend/collectors/hk_us/technical.py
"""Technical data collector for HK/US stocks using yfinance batch download + pandas_ta."""

import json
import logging
from datetime import date, timedelta

import pandas as pd
import pandas_ta as ta
import yfinance as yf

from backend.database import upsert
from backend.models import DailyData

logger = logging.getLogger(__name__)


def _to_yf_symbol(code: str, market: str) -> str:
    if market == "HK":
        return f"{int(code):04d}.HK"
    return code


def _f(row, col):
    val = row.get(col)
    try:
        return round(float(val), 4) if pd.notna(val) else None
    except (TypeError, ValueError):
        return None


def _compute_returns(closes: list[float]) -> dict:
    out = {
        "return_3d": None, "return_5d": None, "return_13d": None,
        "return_20d": None, "return_60d": None, "return_mid": None,
    }
    today_c = closes[-1] if closes else None
    for window, key in [(3, "return_3d"), (5, "return_5d"), (13, "return_13d"),
                        (20, "return_20d"), (60, "return_60d")]:
        if today_c and len(closes) > window and closes[-window - 1]:
            out[key] = round((today_c - closes[-window - 1]) / closes[-window - 1] * 100, 2)
    if len(closes) > 31 and closes[-31] and closes[-6]:
        out["return_mid"] = round((closes[-6] - closes[-31]) / closes[-31] * 100, 2)
    return out


def _detect_patterns(last_row, prev_row, change_pct) -> list[str]:
    tags = []
    ma5 = _f(last_row, "SMA_5");   ma13 = _f(last_row, "SMA_13")
    pma5 = _f(prev_row, "SMA_5");  pma13 = _f(prev_row, "SMA_13")
    if None not in (ma5, ma13, pma5, pma13):
        if ma5 > ma13 and pma5 < pma13:
            tags.append("MA5上穿MA13")
        elif ma5 < ma13 and pma5 > pma13:
            tags.append("MA5下穿MA13")
    vr = _f(last_row, "VOL_RATIO")
    if vr is not None and change_pct is not None and vr > 2 and change_pct > 3:
        tags.append("放量上攻")
    dif = _f(last_row, "MACD_12_26_9");   dea = _f(last_row, "MACDs_12_26_9")
    pdif = _f(prev_row, "MACD_12_26_9");  pdea = _f(prev_row, "MACDs_12_26_9")
    if None not in (dif, dea, pdif, pdea):
        if dif > dea and pdif <= pdea:
            tags.append("MACD金叉")
    return tags


def _analyze_stock(code: str, market: str, today: str, df: pd.DataFrame) -> dict | None:
    """Compute all technical indicators from a pre-fetched DataFrame."""
    if df is None or len(df) < 15:
        return None

    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })

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
    change_pct = (
        round((closes[-1] - closes[-2]) / closes[-2] * 100, 2)
        if len(closes) >= 2 and closes[-2] else None
    )
    returns = _compute_returns(closes)
    tags = _detect_patterns(last, prev, change_pct)

    vol_ma3 = sum(volumes[-3:]) / 3 if len(volumes) >= 3 else None
    vol_ma5 = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else None
    vol_ma13 = sum(volumes[-13:]) / 13 if len(volumes) >= 13 else None
    vol_ma30 = sum(volumes[-30:]) / 30 if len(volumes) >= 30 else None

    close_today = closes[-1]
    is_30d_high = 1 if close_today >= max(closes[-30:]) and len(closes) >= 30 else 0
    is_10d_high = 1 if close_today >= max(closes[-10:]) and len(closes) >= 10 else 0

    ma5_slope3 = None
    ma5_vals = [df.iloc[i].get("SMA_5") for i in range(-4, 0)]
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

    # Also compute heat data from the same DataFrame
    close_prev = closes[-2] if len(closes) >= 2 else None
    heat_change_pct = round((close_today - close_prev) / close_prev * 100, 4) if close_prev else None
    volume_today = volumes[-1] if volumes else None

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
        # Heat data (merged from market_heat collector)
        "turnover_rate": None,  # needs sharesOutstanding, filled by heat/news pass
        "consecutive_limit_up": 0,
    }


def collect_hk_us_technical(session, target_codes: dict[str, str], today: str) -> int:
    """Batch-download all stock histories via yf.download(), then compute indicators.

    This makes ~1 HTTP request per batch instead of 1 per stock.
    """
    if not target_codes:
        logger.warning("No target codes for HK/US technical collection")
        return 0

    today_dt = date.fromisoformat(today)
    start = (today_dt - timedelta(days=180)).isoformat()

    # Build symbol list: code -> yfinance symbol
    code_to_symbol = {}
    for code, market in target_codes.items():
        code_to_symbol[code] = _to_yf_symbol(code, market)

    symbols = list(code_to_symbol.values())
    symbol_to_code = {v: k for k, v in code_to_symbol.items()}

    # Batch download — single HTTP request for all tickers
    logger.info(f"Batch downloading {len(symbols)} tickers via yf.download()...")
    t0 = __import__("time").time()
    try:
        data = yf.download(
            tickers=symbols,
            start=start,
            end=today,
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
    except Exception as e:
        logger.error(f"yf.download() failed: {e}")
        return 0
    elapsed = round(__import__("time").time() - t0, 1)
    logger.info(f"Batch download complete in {elapsed}s")

    # Process each ticker
    results = []
    total = len(symbols)
    for i, symbol in enumerate(symbols, 1):
        code = symbol_to_code[symbol]
        market = target_codes[code]
        try:
            if len(symbols) > 1:
                df = data[symbol].dropna(subset=["Close"])
            else:
                df = data.dropna(subset=["Close"])
            result = _analyze_stock(code, market, today, df)
            if result:
                results.append(result)
        except Exception as e:
            logger.error(f"HK/US technical failed for {code} ({symbol}): {e}")
        if i % 50 == 0 or i == total:
            logger.info(f"HK/US Technical: {i}/{total} processed")

    count = 0
    for record in results:
        try:
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"HK/US Technical upsert failed for {record.get('code')}: {e}")

    session.commit()
    logger.info(f"HK/US technical data collected: {count} stocks")
    return count
