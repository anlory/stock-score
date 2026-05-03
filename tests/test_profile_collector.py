import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import pandas as pd
from backend.models import Stock
from backend.collectors.profile import fetch_profile


def _seed_stock(session, code="000001", **kw):
    defaults = dict(code=code, name="平安银行", market="SZ", is_watchlist=False, index_tags="[]")
    defaults.update(kw)
    session.add(Stock(**defaults))
    session.commit()


@patch("backend.collectors.profile._fetch_concepts")
@patch("backend.collectors.profile._fetch_company_info")
@patch("backend.collectors.profile._fetch_individual_info")
def test_fetch_profile_populates_all_fields(mock_info, mock_company, mock_concepts, db_session):
    _seed_stock(db_session)
    mock_info.return_value = {
        "industry": "银行",
        "total_share": 194.06,
        "float_share": 194.05,
        "list_date": "1991-04-03",
    }
    mock_company.return_value = {
        "chairman": "谢永林",
        "manager": "胡跃飞",
        "setup_date": "1987-12-22",
        "province": "广东",
        "city": "深圳市",
        "introduction": "平安银行股份有限公司",
        "main_business": "吸收公众存款",
        "business": "各项银行业务",
        "website": "",
        "employees": 35000,
        "office": "深圳市福田区",
    }
    mock_concepts.return_value = ["金融改革", "大金融"]

    stock = fetch_profile(db_session, "000001")

    assert stock.industry == "银行"
    assert stock.total_share == 194.06
    assert stock.list_date == "1991-04-03"
    assert "银行业务" in stock.business
    assert stock.chairman == "谢永林"
    assert stock.setup_date == "1987-12-22"
    assert stock.employees == 35000
    assert json.loads(stock.concepts) == ["金融改革", "大金融"]
    assert stock.profile_updated_at is not None


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


@patch("backend.collectors.profile._fetch_concepts")
@patch("backend.collectors.profile._fetch_company_info")
@patch("backend.collectors.profile._fetch_individual_info")
def test_fetch_profile_expired_cache_refetches(mock_info, mock_company, mock_concepts, db_session):
    _seed_stock(
        db_session, industry="银行", business="stale",
        profile_updated_at=datetime.now() - timedelta(days=40),
    )
    mock_info.return_value = {"industry": "银行", "total_share": 1.0, "float_share": 1.0, "list_date": "1991-04-03"}
    mock_company.return_value = {
        "chairman": "", "manager": "", "setup_date": None, "province": "", "city": "",
        "introduction": None, "main_business": None, "business": "fresh",
        "website": "", "employees": None, "office": "",
    }
    mock_concepts.return_value = []

    stock = fetch_profile(db_session, "000001")
    assert stock.business == "fresh"


@patch("backend.collectors.profile._fetch_individual_info", side_effect=RuntimeError("boom"))
def test_fetch_profile_on_error_keeps_existing(mock_info, db_session):
    _seed_stock(db_session, business="kept")
    stock = fetch_profile(db_session, "000001")
    assert stock.business == "kept"
