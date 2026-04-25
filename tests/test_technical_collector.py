# tests/test_technical_collector.py
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from backend.collectors.technical import collect_technical
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


@patch("backend.collectors.technical.get_pro")
def test_collect_technical_skips_insufficient_data(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro
    mock_pro.daily.return_value = _make_daily_df("000001.SZ", n=10)

    count = collect_technical(db_session, {"000001"})
    assert count == 0
