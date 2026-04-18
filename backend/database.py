from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from backend.config import DATABASE_URL, ensure_dirs
from backend.models import Base

ensure_dirs()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_session():
    """FastAPI Depends generator - yields and auto-closes session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def get_db_session():
    """Direct session factory for non-FastAPI code (scheduler, tests). Caller must close."""
    return SessionLocal()

def upsert(session, model, data: dict, index_elements: list):
    """Execute INSERT OR UPDATE. Caller is responsible for session.commit()."""
    stmt = sqlite_insert(model).values(**data)
    update_cols = {k: stmt.excluded[k] for k in data if k not in index_elements}
    stmt = stmt.on_conflict_do_update(index_elements=index_elements, set_=update_cols)
    session.execute(stmt)

def seed_strategies(session):
    """Insert preset strategies if not already present."""
    from backend.models import Strategy
    strategies = [
        {
            "name": "short_term",
            "display_name": "短线策略",
            "technical_weight": 0.35,
            "capital_weight": 0.25,
            "fundamental_weight": 0.0,
            "news_weight": 0.10,
            "heat_weight": 0.30,
        },
        {
            "name": "trend",
            "display_name": "趋势策略",
            "technical_weight": 0.40,
            "capital_weight": 0.30,
            "fundamental_weight": 0.05,
            "news_weight": 0.05,
            "heat_weight": 0.20,
        },
        {
            "name": "value",
            "display_name": "价值策略",
            "technical_weight": 0.20,
            "capital_weight": 0.15,
            "fundamental_weight": 0.50,
            "news_weight": 0.10,
            "heat_weight": 0.05,
        },
    ]
    for s in strategies:
        upsert(session, Strategy, s, ["name"])
    session.commit()
