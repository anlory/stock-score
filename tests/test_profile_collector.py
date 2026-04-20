import json
from datetime import datetime, timedelta
from unittest.mock import patch
from backend.models import Stock
from backend.collectors.profile import fetch_profile


def _seed_stock(session, code="000001", **kw):
    defaults = dict(code=code, name="平安银行", market="SZ", is_watchlist=False, index_tags="[]")
    defaults.update(kw)
    session.add(Stock(**defaults))
    session.commit()


@patch("backend.collectors.profile._fetch_individual_info")
@patch("backend.collectors.profile._fetch_business")
@patch("backend.collectors.profile._fetch_concepts")
def test_fetch_profile_populates_all_fields(mock_concepts, mock_business, mock_info, db_session):
    _seed_stock(db_session)
    mock_info.return_value = {
        "industry": "银行",
        "total_share": 194.06,
        "float_share": 194.05,
        "list_date": "1991-04-03",
    }
    mock_business.return_value = "主营业务：各项银行业务..."
    mock_concepts.return_value = ["金融改革", "大金融"]

    stock = fetch_profile(db_session, "000001")

    assert stock.industry == "银行"
    assert stock.total_share == 194.06
    assert stock.list_date == "1991-04-03"
    assert "银行业务" in stock.business
    assert json.loads(stock.concepts) == ["金融改革", "大金融"]
    assert stock.profile_updated_at is not None
    mock_info.assert_called_once()


@patch("backend.collectors.profile._fetch_individual_info")
def test_fetch_profile_cache_hit_skips_api(mock_info, db_session):
    _seed_stock(
        db_session,
        industry="银行",
        business="cached",
        profile_updated_at=datetime.now() - timedelta(days=5),
    )

    stock = fetch_profile(db_session, "000001")

    assert stock.business == "cached"
    mock_info.assert_not_called()


@patch("backend.collectors.profile._fetch_individual_info")
@patch("backend.collectors.profile._fetch_business")
@patch("backend.collectors.profile._fetch_concepts")
def test_fetch_profile_expired_cache_refetches(mock_concepts, mock_business, mock_info, db_session):
    _seed_stock(
        db_session,
        industry="银行",
        business="stale",
        profile_updated_at=datetime.now() - timedelta(days=40),
    )
    mock_info.return_value = {"industry": "银行", "total_share": 1.0, "float_share": 1.0, "list_date": "1991-04-03"}
    mock_business.return_value = "fresh"
    mock_concepts.return_value = []

    stock = fetch_profile(db_session, "000001")
    assert stock.business == "fresh"


@patch("backend.collectors.profile._fetch_individual_info", side_effect=RuntimeError("boom"))
def test_fetch_profile_on_error_keeps_existing(mock_info, db_session):
    _seed_stock(db_session, business="kept")
    stock = fetch_profile(db_session, "000001")
    assert stock.business == "kept"
