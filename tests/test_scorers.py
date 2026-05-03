from backend.scorers.base import percentile_score, clamp, safe_float
from backend.scorers.technical import TechnicalScorer
from backend.scorers.capital import CapitalScorer
from backend.scorers.fundamental import FundamentalScorer
from backend.scorers.news import NewsScorer
from backend.scorers.market_heat import HeatScorer

def test_percentile_higher():
    # (below + 0.5*equal) / N: max→90, min→10 with N=5
    values = [10, 20, 30, 40, 50]
    assert percentile_score(50, values, True) == 90
    assert percentile_score(10, values, True) == 10

def test_percentile_lower():
    values = [10, 20, 30, 40, 50]
    assert percentile_score(10, values, False) == 90
    assert percentile_score(50, values, False) == 10

def test_percentile_all_equal_returns_50():
    values = [42, 42, 42, 42, 42]
    assert percentile_score(42, values, True) == 50
    assert percentile_score(42, values, False) == 50

def test_percentile_empty():
    assert percentile_score(10, [], True) == 50

def test_percentile_none():
    assert percentile_score(None, [1, 2, 3]) == 50

def test_clamp():
    assert clamp(150, 0, 100) == 100
    assert clamp(-10, 0, 100) == 0
    assert clamp(50, 0, 100) == 50

def test_safe_float():
    assert safe_float("3.14") == 3.14
    assert safe_float(None) is None
    assert safe_float("abc") is None
    assert safe_float("abc", 0) == 0

UNIVERSE = {
    "main_inflow_today": [100, 200, 300, 400, 500],
    "main_inflow_5d": [100, 200, 300, 400, 500],
    "super_large_inflow": [50, 100, 150, 200, 250],
    "pe": [10, 20, 30, 40, 50],
    "pb": [1, 2, 3, 4, 5],
    "roe": [5, 10, 15, 20, 25],
    "profit_growth_yoy": [5, 10, 15, 20, 25],
}

def test_technical_bullish():
    data = {"close": 10.0, "ma5": 9.8, "ma13": 9.5, "ma30": 9.0,
            "prev_ma5": 9.6, "prev_ma13": 9.4, "prev_ma30": 8.9,
            "return_3d": 5.0, "return_5d": 6.0, "return_13d": 15.0,
            "return_mid": 22.0, "ma5_slope3": 2.0, "is_10d_high": 1,
            "is_30d_high": 1,
            "vol_ma3": 500, "vol_ma5": 600, "vol_ma13": 300, "vol_ma30": 400,
            "close_above_ma5_5d": 5, "last_close_above_ma5": 1}
    score = TechnicalScorer().score(data)
    assert 0 <= score <= 100
    assert score >= 80, f"bullish should score >= 80, got {score}"

def test_technical_bearish():
    data = {"close": 8.0, "ma5": 9.0, "ma13": 9.5, "ma30": 10.0,
            "prev_ma5": 9.2, "prev_ma13": 9.4, "prev_ma30": 9.8,
            "return_3d": -3.0, "return_5d": -5.0, "return_13d": -10.0,
            "return_mid": -15.0, "ma5_slope3": -1.5, "is_10d_high": 0,
            "is_30d_high": 0,
            "vol_ma3": 300, "vol_ma5": 350, "vol_ma13": 500, "vol_ma30": 450,
            "close_above_ma5_5d": 0, "last_close_above_ma5": 0}
    score = TechnicalScorer().score(data)
    assert score < 20, f"bearish should score < 20, got {score}"

def test_technical_no_data():
    score = TechnicalScorer().score({})
    assert score == 0.0

def test_technical_pullback_channel():
    """Channel A: pullback to MA13 + back above MA5"""
    data = {"close": 9.7, "ma5": 9.65, "ma13": 9.6, "ma30": 9.2,
            "prev_ma5": 9.7, "prev_ma13": 9.6, "prev_ma30": 9.2,
            "return_3d": -1.0, "return_5d": 1.0, "return_13d": 5.0,
            "return_mid": 8.0, "ma5_slope3": 0.5, "is_10d_high": 0,
            "is_30d_high": 0,
            "vol_ma3": 200, "vol_ma5": 250, "vol_ma13": 300, "vol_ma30": 350,
            "close_above_ma5_5d": 3, "last_close_above_ma5": 1}
    score = TechnicalScorer().score(data)
    assert 20 <= score <= 60

def test_capital_range():
    data = {"main_inflow_today": 400, "main_inflow_5d": 400,
            "super_large_inflow": 200, "north_inflow": 100, "margin_net_buy": 50}
    score = CapitalScorer().score(data, UNIVERSE)
    assert 0 <= score <= 100

def test_fundamental_range():
    data = {"pe": 15.0, "pb": 1.5, "roe": 20.0, "profit_growth_yoy": 20.0}
    score = FundamentalScorer().score(data, UNIVERSE)
    assert 0 <= score <= 100

def test_news_buy_rating():
    data = {"report_count": 5, "report_rating": "买入", "news_sentiment": 0.8}
    score = NewsScorer().score(data)
    assert score > 70

def test_heat_range():
    data = {"change_pct": 3.5, "turnover_rate": 5.0, "volume_ratio": 1.5,
            "consecutive_limit_up": 1, "sector_heat_rank": 5}
    score = HeatScorer().score(data, {})
    assert 0 <= score <= 100
