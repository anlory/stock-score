from unittest.mock import MagicMock
from backend.engine import ScoreEngine

SAMPLE = {
    "close": 10.0, "ma5": 9.8, "ma13": 9.5, "ma30": 9.0,
    "macd_dif": 0.1, "macd_dea": 0.05, "macd_bar": 0.1, "rsi14": 60.0,
    "kdj_k": 70.0, "kdj_d": 65.0, "kdj_j": 80.0,
    "boll_upper": 11.0, "boll_mid": 10.0, "boll_lower": 9.0, "volume_ratio": 1.5,
    "main_inflow_today": 400.0, "main_inflow_5d": 300.0,
    "super_large_inflow": 200.0, "north_inflow": 50.0, "margin_net_buy": 30.0,
    "pe": 15.0, "pb": 1.5, "roe": 18.0, "profit_growth_yoy": 20.0, "market_cap": 50e8,
    "report_count": 3, "report_rating": "买入", "news_sentiment": 0.7,
    "change_pct": 3.5, "turnover_rate": 5.0, "consecutive_limit_up": 0, "sector_heat_rank": 5,
}

STRATEGY = MagicMock(
    technical_weight=0.40, capital_weight=0.30,
    fundamental_weight=0.05, news_weight=0.05, heat_weight=0.20,
)


def test_score_stock_returns_all_fields():
    engine = ScoreEngine()
    result = engine.score_stock(SAMPLE, [SAMPLE], STRATEGY)
    assert "total_score" in result
    assert 0 <= result["total_score"] <= 100
    for k in ["technical_score", "capital_score", "fundamental_score", "news_score", "heat_score"]:
        assert k in result
        assert 0 <= result[k] <= 100


def test_total_equals_weighted_sum():
    engine = ScoreEngine()
    result = engine.score_stock(SAMPLE, [SAMPLE], STRATEGY)
    expected = (
        result["technical_score"] * 0.40 +
        result["capital_score"] * 0.30 +
        result["fundamental_score"] * 0.05 +
        result["news_score"] * 0.05 +
        result["heat_score"] * 0.20
    )
    assert abs(result["total_score"] - expected) < 0.01
