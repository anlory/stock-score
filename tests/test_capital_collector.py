# tests/test_capital_collector.py
import pandas as pd
from unittest.mock import patch, MagicMock
from backend.collectors.capital import collect_capital
from backend.models import DailyData


@patch("backend.collectors.capital.get_pro")
def test_collect_capital_writes_inflow(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro

    # Side effects: first call = today's full market, second call = per-stock 5-day
    mock_pro.moneyflow.side_effect = [
        pd.DataFrame([{
            "ts_code": "000001.SZ",
            "trade_date": "20260425",
            "buy_lg_amount": 500.0,
            "buy_elg_amount": 300.0,
            "net_mf_amount": 200.0,
        }]),
        pd.DataFrame([
            {"ts_code": "000001.SZ", "trade_date": "20260421", "net_mf_amount": 100.0},
            {"ts_code": "000001.SZ", "trade_date": "20260422", "net_mf_amount": 150.0},
            {"ts_code": "000001.SZ", "trade_date": "20260423", "net_mf_amount": -50.0},
            {"ts_code": "000001.SZ", "trade_date": "20260424", "net_mf_amount": 80.0},
            {"ts_code": "000001.SZ", "trade_date": "20260425", "net_mf_amount": 200.0},
        ]),
    ]

    count = collect_capital(db_session, {"000001"})

    assert count == 1
    row = db_session.query(DailyData).filter_by(code="000001").first()
    assert row.main_inflow_today == 800.0   # 500 + 300
    assert row.super_large_inflow == 300.0
    assert abs(row.main_inflow_5d - 480.0) < 0.01  # 100+150-50+80+200
