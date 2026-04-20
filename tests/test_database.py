import sqlite3
import tempfile
import os
from sqlalchemy import create_engine, text
from backend.database import upsert
from backend.models.stock import Stock

def test_upsert_creates_record(db_session):
    data = {"code": "000001", "name": "平安银行", "market": "SZ", "is_watchlist": True, "index_tags": "[]"}
    upsert(db_session, Stock, data, ["code"])
    db_session.commit()
    result = db_session.get(Stock, "000001")
    assert result.name == "平安银行"

def test_upsert_updates_existing(db_session):
    data = {"code": "000001", "name": "平安银行", "market": "SZ", "is_watchlist": True, "index_tags": "[]"}
    upsert(db_session, Stock, data, ["code"])
    db_session.commit()
    data["name"] = "平安银行(更新)"
    upsert(db_session, Stock, data, ["code"])
    db_session.commit()
    result = db_session.get(Stock, "000001")
    assert result.name == "平安银行(更新)"

def test_upsert_daily_data(db_session):
    from backend.models.daily_data import DailyData
    data = {"code": "000001", "date": "2026-04-18", "close": 10.0, "ma5": 9.8}
    upsert(db_session, DailyData, data, ["code", "date"])
    db_session.commit()
    result = db_session.query(DailyData).filter_by(code="000001", date="2026-04-18").first()
    assert result.close == 10.0


def test_migrate_add_columns_adds_missing():
    from backend.database import _migrate_add_columns
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE stocks (code TEXT PRIMARY KEY, name TEXT)")
        conn.commit()
        conn.close()

        engine = create_engine(f"sqlite:///{path}")
        _migrate_add_columns(engine, "stocks", [
            ("industry", "VARCHAR"),
            ("total_share", "FLOAT"),
        ])

        with engine.connect() as c:
            cols = [row[1] for row in c.execute(text("PRAGMA table_info(stocks)"))]
        assert "industry" in cols
        assert "total_share" in cols
    finally:
        os.unlink(path)


def test_migrate_add_columns_idempotent():
    from backend.database import _migrate_add_columns
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE stocks (code TEXT PRIMARY KEY, industry VARCHAR)")
        conn.commit()
        conn.close()

        engine = create_engine(f"sqlite:///{path}")
        _migrate_add_columns(engine, "stocks", [("industry", "VARCHAR")])
        _migrate_add_columns(engine, "stocks", [("industry", "VARCHAR")])

        with engine.connect() as c:
            cols = [row[1] for row in c.execute(text("PRAGMA table_info(stocks)"))]
        assert cols.count("industry") == 1
    finally:
        os.unlink(path)
