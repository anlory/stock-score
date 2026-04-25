import pandas as pd
from unittest.mock import patch, MagicMock
from backend.collectors.market_heat import collect_market_heat
from backend.models import DailyData


@patch("backend.collectors.market_heat.get_pro")
def test_collect_market_heat_writes_fields(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro

    mock_pro.daily.return_value = pd.DataFrame([{
        "ts_code": "000001.SZ", "trade_date": "20260425", "pct_chg": 2.5, "vol": 1e6,
    }])
    mock_pro.daily_basic.return_value = pd.DataFrame([{
        "ts_code": "000001.SZ", "trade_date": "20260425",
        "turnover_rate": 3.2, "volume_ratio": 1.8,
    }])
    mock_pro.trade_cal.return_value = pd.DataFrame({
        "cal_date": ["20260416", "20260417", "20260420", "20260421", "20260422",
                     "20260423", "20260424", "20260425"],
        "is_open": ["1"] * 8,
    })
    # No limit-up stocks today
    mock_pro.limit_list_d.return_value = pd.DataFrame(columns=["ts_code", "trade_date"])

    count = collect_market_heat(db_session, {"000001"})

    assert count == 1
    row = db_session.query(DailyData).filter_by(code="000001").first()
    assert row.change_pct == 2.5
    assert row.turnover_rate == 3.2
    assert row.volume_ratio == 1.8
    assert row.consecutive_limit_up == 0


@patch("backend.collectors.market_heat.get_pro")
def test_consecutive_limit_up_counted(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro

    mock_pro.daily.return_value = pd.DataFrame([{
        "ts_code": "000001.SZ", "trade_date": "20260425", "pct_chg": 9.9, "vol": 2e6,
    }])
    mock_pro.daily_basic.return_value = pd.DataFrame([{
        "ts_code": "000001.SZ", "trade_date": "20260425",
        "turnover_rate": 5.0, "volume_ratio": 3.0,
    }])
    mock_pro.trade_cal.return_value = pd.DataFrame({
        "cal_date": ["20260421", "20260422", "20260423", "20260424", "20260425"],
        "is_open": ["1"] * 5,
    })

    # Stock hit limit-up for all days
    def limit_side_effect(trade_date, **kw):
        return pd.DataFrame([{"ts_code": "000001.SZ", "trade_date": trade_date}])

    mock_pro.limit_list_d.side_effect = limit_side_effect

    count = collect_market_heat(db_session, {"000001"})
    assert count == 1
    row = db_session.query(DailyData).filter_by(code="000001").first()
    assert row.consecutive_limit_up == 5
