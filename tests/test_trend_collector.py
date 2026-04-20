import json
from unittest.mock import patch
from backend.models import Stock, DailyData
from backend.collectors.trend import (
    _compute_returns,
    _detect_patterns,
    collect_trend,
)


def test_compute_returns_basic():
    # close prices chronological, oldest first. Today's close = 110, 5 days ago = 100.
    closes = [100.0] * 60 + [105.0, 106.0, 107.0, 108.0, 110.0]  # length 65
    r = _compute_returns(closes)
    assert round(r["return_5d"], 2) == 10.0   # (110-100)/100
    assert round(r["return_20d"], 2) == 10.0
    assert round(r["return_60d"], 2) == 10.0


def test_compute_returns_insufficient_history_returns_none():
    closes = [100.0, 101.0, 102.0]
    r = _compute_returns(closes)
    assert r["return_5d"] is None
    assert r["return_20d"] is None
    assert r["return_60d"] is None


def test_detect_patterns_ma5_cross_up():
    d = {
        "ma5": 10.5, "ma13": 10.3, "prev_ma5": 10.1, "prev_ma13": 10.3,
        "volume_ratio": 1.0, "change_pct": 0.5,
        "macd_dif": 0.1, "macd_dea": 0.2,
    }
    tags = _detect_patterns(d, prev_macd_dif=0.0, prev_macd_dea=0.0)
    assert "MA5上穿MA13" in tags


def test_detect_patterns_ma5_cross_down():
    d = {"ma5": 10.1, "ma13": 10.3, "prev_ma5": 10.5, "prev_ma13": 10.3,
         "volume_ratio": 1.0, "change_pct": 0.0}
    tags = _detect_patterns(d, prev_macd_dif=None, prev_macd_dea=None)
    assert "MA5下穿MA13" in tags


def test_detect_patterns_volume_surge():
    d = {"ma5": 10.0, "ma13": 10.0, "prev_ma5": 10.0, "prev_ma13": 10.0,
         "volume_ratio": 2.5, "change_pct": 3.5}
    tags = _detect_patterns(d, prev_macd_dif=None, prev_macd_dea=None)
    assert "放量上攻" in tags


def test_detect_patterns_macd_gold_cross():
    d = {"ma5": 10.0, "ma13": 10.0, "prev_ma5": 10.0, "prev_ma13": 10.0,
         "volume_ratio": 1.0, "change_pct": 0.0,
         "macd_dif": 0.3, "macd_dea": 0.2}
    tags = _detect_patterns(d, prev_macd_dif=0.1, prev_macd_dea=0.2)
    assert "MACD金叉" in tags


@patch("backend.collectors.trend._fetch_industry_changes")
@patch("backend.collectors.trend.fetch_kline")
def test_collect_trend_writes_daily_data(mock_kline, mock_industry, db_session):
    db_session.add(Stock(code="000001", name="平安银行", market="SZ", industry="银行", index_tags="[]"))
    today = "2026-04-20"
    db_session.add(DailyData(
        code="000001", date=today,
        ma5=10.5, ma13=10.3, prev_ma5=10.1, prev_ma13=10.3,
        volume_ratio=1.0, change_pct=0.5,
        macd_dif=0.1, macd_dea=0.2,
    ))
    db_session.commit()

    closes = [100.0] * 60 + [105.0, 106.0, 107.0, 108.0, 110.0]
    mock_kline.return_value = [{"date": f"2026-01-{i%30+1:02d}", "close": c}
                               for i, c in enumerate(closes)]
    mock_industry.return_value = {"change": 0.8, "change_5d": 2.1, "change_20d": -0.5}

    count = collect_trend(db_session, {"000001"}, today=today)

    assert count == 1
    row = db_session.query(DailyData).filter_by(code="000001", date=today).one()
    assert row.return_5d is not None
    assert row.industry_change == 0.8
    tags = json.loads(row.pattern_tags or "[]")
    assert "MA5上穿MA13" in tags
