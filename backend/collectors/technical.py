import logging
from datetime import date
import pandas as pd
import pandas_ta as ta
from backend.database import upsert
from backend.models import DailyData
from backend.collectors.tencent_kline import fetch_kline

logger = logging.getLogger(__name__)


def collect_technical(session, target_codes: set[str] = None):
    """Fetch K-line via Tencent API, compute technical indicators with pandas_ta."""
    today = date.today().isoformat()

    codes = sorted(target_codes) if target_codes else []
    if not codes:
        logger.warning("No target codes for technical collection")
        return 0

    count = 0
    for code in codes:
        try:
            rows = fetch_kline(code, days=90)
            if len(rows) < 15:
                continue

            df = pd.DataFrame(rows)
            df["date_dt"] = pd.to_datetime(df["date"])

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
            record = {
                "code": code,
                "date": today,
                "close": _f(last, "close"),
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
            }
            upsert(session, DailyData, record, ["code", "date"])
            count += 1
        except Exception as e:
            logger.error(f"Technical failed for {code}: {e}")

    session.commit()
    logger.info(f"Technical data collected: {count} stocks")
    return count


def _f(row, col):
    val = row.get(col)
    try:
        return round(float(val), 4) if pd.notna(val) else None
    except (TypeError, ValueError):
        return None
