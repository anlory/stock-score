from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from backend.config import DATABASE_URL, ensure_dirs
from backend.models import Base

ensure_dirs()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30})

# Enable WAL mode for better concurrent write performance
with engine.connect() as conn:
    conn.execute(text("PRAGMA journal_mode=WAL"))
    conn.execute(text("PRAGMA busy_timeout=30000"))
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def _migrate_add_columns(eng, table: str, columns: list[tuple[str, str]]):
    """SQLite-only: add columns that don't already exist. columns = [(name, sql_type), ...]."""
    with eng.connect() as conn:
        existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
        if not existing:
            return
        for name, sql_type in columns:
            if name not in existing:
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {sql_type}'))
        conn.commit()


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_add_columns(engine, "stocks", [
        ("business", "TEXT"),
        ("industry", "VARCHAR"),
        ("concepts", "TEXT"),
        ("total_share", "FLOAT"),
        ("float_share", "FLOAT"),
        ("list_date", "VARCHAR"),
        ("total_mv", "FLOAT"),
        ("float_mv", "FLOAT"),
        ("pe", "FLOAT"),
        ("pb", "FLOAT"),
        ("profile_updated_at", "DATETIME"),
    ])
    _migrate_add_columns(engine, "daily_data", [
        ("return_5d", "FLOAT"),
        ("return_20d", "FLOAT"),
        ("return_60d", "FLOAT"),
        ("industry_change", "FLOAT"),
        ("industry_change_5d", "FLOAT"),
        ("industry_change_20d", "FLOAT"),
        ("pattern_tags", "TEXT"),
    ])

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
