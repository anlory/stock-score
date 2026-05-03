import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import backend.collectors.tushare_client as _tc

@pytest.fixture(autouse=True)
def disable_ts_rate_limit():
    """Disable tushare rate limiter during tests."""
    original = _tc._TS_MIN_INTERVAL
    _tc._TS_MIN_INTERVAL = 0
    yield
    _tc._TS_MIN_INTERVAL = original


@pytest.fixture
def db_session():
    from backend.models import Base
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()
