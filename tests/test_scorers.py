from backend.scorers.base import percentile_score, clamp, safe_float
from backend.scorers.technical import TechnicalScorer
from backend.scorers.capital import CapitalScorer
from backend.scorers.fundamental import FundamentalScorer
from backend.scorers.news import NewsScorer
from backend.scorers.market_heat import HeatScorer

def test_percentile_higher():
    values = [10, 20, 30, 40, 50]
    assert percentile_score(50, values, True) == 100
    assert percentile_score(10, values, True) == 0

def test_percentile_lower():
    values = [10, 20, 30, 40, 50]
    assert percentile_score(10, values, False) == 100
    assert percentile_score(50, values, False) == 0

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
            "macd_dif": 0.1, "macd_dea": 0.05, "macd_bar": 0.1,
            "rsi14": 60.0, "kdj_k": 70.0, "kdj_d": 65.0, "kdj_j": 80.0,
            "boll_upper": 11.0, "boll_mid": 10.0, "boll_lower": 9.0, "volume_ratio": 1.5}
    score = TechnicalScorer().score(data)
    assert 0 <= score <= 100
    assert score > 50

def test_technical_bearish():
    data = {"close": 8.0, "ma5": 9.0, "ma13": 9.5, "ma30": 10.0,
            "macd_dif": -0.1, "macd_dea": 0.05, "macd_bar": -0.2,
            "rsi14": 25.0, "kdj_k": 20.0, "kdj_d": 30.0, "kdj_j": 5.0,
            "boll_upper": 11.0, "boll_mid": 9.5, "boll_lower": 8.5, "volume_ratio": 0.5}
    score = TechnicalScorer().score(data)
    assert score < 50

def test_technical_no_data():
    assert TechnicalScorer().score({}) == 50.0

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
