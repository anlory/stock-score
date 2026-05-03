# tests/test_capital_collector.py
import pandas as pd
from unittest.mock import patch, MagicMock
from backend.collectors.capital import collect_capital
from backend.models import DailyData

TODAY_TS = "20260425"

def _make_flow_df(today_ts=TODAY_TS):
    return pd.DataFrame([
        {"ts_code": "000001.SZ", "trade_date": "20260421", "buy_elg_amount": 100.0, "sell_elg_amount": 50.0, "net_mf_amount": 100.0},
        {"ts_code": "000001.SZ", "trade_date": "20260422", "buy_elg_amount": 200.0, "sell_elg_amount": 80.0, "net_mf_amount": 150.0},
        {"ts_code": "000001.SZ", "trade_date": "20260423", "buy_elg_amount": 60.0,  "sell_elg_amount": 90.0, "net_mf_amount": -50.0},
        {"ts_code": "000001.SZ", "trade_date": "20260424", "buy_elg_amount": 120.0, "sell_elg_amount": 40.0, "net_mf_amount": 80.0},
        {"ts_code": "000001.SZ", "trade_date": today_ts,   "buy_elg_amount": 300.0, "sell_elg_amount": 100.0, "net_mf_amount": 200.0},
    ])


@patch("backend.collectors.capital.get_pro")
def test_collect_capital_writes_inflow(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro
    mock_pro.moneyflow.return_value = _make_flow_df()

    count = collect_capital(db_session, {"000001"}, today="2026-04-25")

    assert count == 1
    row = db_session.query(DailyData).filter_by(code="000001").first()
    assert row.main_inflow_today == 200.0          # net_mf_amount of today
    assert row.super_large_inflow == 200.0         # buy_elg - sell_elg = 300 - 100
    assert abs(row.main_inflow_5d - 480.0) < 0.01  # sum of 5 net_mf_amount


@patch("backend.collectors.capital.get_pro")
def test_collect_capital_empty_skips_upsert(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro
    mock_pro.moneyflow.return_value = pd.DataFrame()

    count = collect_capital(db_session, {"000001"}, today="2026-04-25")
    assert count == 0  # no data → no upsert
