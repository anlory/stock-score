# tests/test_fundamental_collector.py
import pandas as pd
from unittest.mock import patch, MagicMock
from backend.collectors.fundamental import collect_fundamental, _latest_fina_period
from backend.models import DailyData


def test_latest_fina_period_early_year():
    assert _latest_fina_period(2026, 3) == "20250930"


def test_latest_fina_period_mid_year():
    assert _latest_fina_period(2026, 6) == "20251231"


def test_latest_fina_period_q3():
    assert _latest_fina_period(2026, 9) == "20260630"


def test_latest_fina_period_q4():
    assert _latest_fina_period(2026, 11) == "20260930"


@patch("backend.collectors.fundamental.get_pro")
def test_collect_fundamental_writes_pe_pb_roe(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro

    mock_pro.daily_basic.return_value = pd.DataFrame([{
        "ts_code": "000001.SZ", "trade_date": "20260425",
        "pe_ttm": 8.5, "pb": 0.9, "total_mv": 2000000.0,  # 万元
    }])
    mock_pro.fina_indicator.return_value = pd.DataFrame([{
        "ts_code": "000001.SZ", "end_date": "20250930",
        "roe": 12.3, "netprofit_yoy": 8.5,
    }])

    count = collect_fundamental(db_session, {"000001"})

    assert count == 1
    row = db_session.query(DailyData).filter_by(code="000001").first()
    assert row.pe == 8.5
    assert row.pb == 0.9
    assert abs(row.market_cap - 200.0) < 0.01  # 2000000万 / 10000 = 200亿
    assert row.roe == 12.3
    assert row.profit_growth_yoy == 8.5
