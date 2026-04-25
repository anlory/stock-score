import pandas as pd
from unittest.mock import patch, MagicMock
from backend.collectors.universe import sync_universe
from backend.models import Stock


@patch("backend.collectors.universe.get_pro")
def test_sync_universe_inserts_index_stocks(mock_get_pro, db_session):
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro

    mock_pro.stock_basic.return_value = pd.DataFrame([{
        "ts_code": "600519.SH", "name": "贵州茅台", "industry": "白酒", "market": "主板",
    }])
    mock_pro.index_member.return_value = pd.DataFrame([{
        "con_code": "600519.SH", "con_name": "贵州茅台",
    }])
    mock_pro.ths_index.return_value = pd.DataFrame([{
        "ts_code": "885096.TI", "name": "白酒",
    }])
    mock_pro.ths_daily.return_value = pd.DataFrame(columns=["ts_code", "pct_change"])

    total = sync_universe(db_session)

    assert total >= 1
    stock = db_session.query(Stock).filter_by(code="600519").first()
    assert stock is not None
    assert stock.name == "贵州茅台"
    assert stock.industry == "白酒"


@patch("backend.collectors.universe.get_pro")
def test_sync_universe_populates_industry_map(mock_get_pro, db_session):
    from backend.collectors import tushare_client
    mock_pro = MagicMock()
    mock_get_pro.return_value = mock_pro

    mock_pro.stock_basic.return_value = pd.DataFrame(columns=["ts_code", "name", "industry", "market"])
    mock_pro.index_member.return_value = pd.DataFrame(columns=["con_code", "con_name"])
    mock_pro.ths_index.return_value = pd.DataFrame([{
        "ts_code": "885096.TI", "name": "银行",
    }])
    mock_pro.ths_daily.return_value = pd.DataFrame(columns=["ts_code", "pct_change"])

    sync_universe(db_session)

    assert tushare_client.INDUSTRY_TS_CODE_MAP.get("银行") == "885096.TI"
