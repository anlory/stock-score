# tests/test_technical_collector.py
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from backend.collectors.technical import collect_technical, _compute_returns, _detect_patterns, _f
from backend.models import DailyData


def _make_daily_df(ts_code="000001.SZ", n=90):
    """Return tushare-format daily DataFrame with enough rows for indicators."""
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    closes = 10.0 + np.cumsum(np.random.randn(n) * 0.1)
    df = pd.DataFrame({
        "ts_code": ts_code,
        "trade_date": [d.strftime("%Y%m%d") for d in dates],
        "open": closes * 0.99,
        "high": closes * 1.01,
        "low": closes * 0.98,
        "close": closes,
        "pre_close": closes * 0.99,
        "change": closes * 0.01,
        "pct_chg": 1.0,
        "vol": 1e6,
        "amount": 1e7,
    })
    return df.sort_values("trade_date").reset_index(drop=True)


@patch("backend.collectors.technical.get_pro")
def test_collect_technical_writes_indicators(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro
    mock_pro.daily.return_value = _make_daily_df("000001.SZ")

    count = collect_technical(db_session, {"000001"})

    assert count == 1
    row = db_session.query(DailyData).filter_by(code="000001").first()
    assert row is not None
    assert row.close is not None
    assert row.ma5 is not None
    assert row.macd_dif is not None
    assert row.rsi14 is not None
    assert row.return_3d is not None
    assert row.return_13d is not None
    assert row.vol_ma5 is not None
    assert row.vol_ma13 is not None
    assert row.ma5_slope3 is not None


@patch("backend.collectors.technical.get_pro")
def test_collect_technical_skips_insufficient_data(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro
    mock_pro.daily.return_value = _make_daily_df("000001.SZ", n=10)

    count = collect_technical(db_session, {"000001"})
    assert count == 0


def test_compute_returns_basic():
    closes = [100.0] * 60 + [105.0, 106.0, 107.0, 108.0, 110.0]
    r = _compute_returns(closes)
    # return_3d: close[-1] vs close[-4] (3 days ago)
    assert round(r["return_3d"], 2) == round((110 - 106) / 106 * 100, 2)
    assert round(r["return_5d"], 2) == 10.0
    assert round(r["return_13d"], 2) == 10.0
    assert round(r["return_20d"], 2) == 10.0
    assert round(r["return_60d"], 2) == 10.0
    assert r["return_mid"] is not None


def test_compute_returns_insufficient_history():
    closes = [100.0, 101.0, 102.0]
    r = _compute_returns(closes)
    assert r["return_3d"] is None
    assert r["return_5d"] is None
    assert r["return_13d"] is None
    assert r["return_mid"] is None


def test_detect_patterns_ma5_cross_up():
    last = pd.Series({"SMA_5": 10.5, "SMA_13": 10.3, "VOL_RATIO": 1.0,
                      "MACD_12_26_9": 0.1, "MACDs_12_26_9": 0.2})
    prev = pd.Series({"SMA_5": 10.1, "SMA_13": 10.3, "VOL_RATIO": 1.0,
                      "MACD_12_26_9": 0.0, "MACDs_12_26_9": 0.0})
    tags = _detect_patterns(last, prev, change_pct=0.5)
    assert "MA5上穿MA13" in tags


def test_detect_patterns_volume_surge():
    last = pd.Series({"SMA_5": 10.0, "SMA_13": 10.0, "VOL_RATIO": 2.5,
                      "MACD_12_26_9": 0.1, "MACDs_12_26_9": 0.2})
    prev = pd.Series({"SMA_5": 10.0, "SMA_13": 10.0, "VOL_RATIO": 1.0,
                      "MACD_12_26_9": 0.1, "MACDs_12_26_9": 0.2})
    tags = _detect_patterns(last, prev, change_pct=3.5)
    assert "放量上攻" in tags


def test_detect_patterns_macd_gold_cross():
    last = pd.Series({"SMA_5": 10.0, "SMA_13": 10.0, "VOL_RATIO": 1.0,
                      "MACD_12_26_9": 0.3, "MACDs_12_26_9": 0.2})
    prev = pd.Series({"SMA_5": 10.0, "SMA_13": 10.0, "VOL_RATIO": 1.0,
                      "MACD_12_26_9": 0.1, "MACDs_12_26_9": 0.2})
    tags = _detect_patterns(last, prev, change_pct=0.0)
    assert "MACD金叉" in tags
