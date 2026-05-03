from backend.models import Stock, DailyData
from backend.collectors.trend import collect_trend


def test_collect_trend_returns_zero(db_session):
    db_session.add(Stock(code="000001", name="平安银行", market="SZ", industry="银行", index_tags="[]"))
    db_session.add(DailyData(code="000001", date="2026-04-25"))
    db_session.commit()

    count = collect_trend(db_session, {"000001"}, today="2026-04-25")
    assert count == 0
