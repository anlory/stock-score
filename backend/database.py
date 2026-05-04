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
        ("chairman", "VARCHAR"),
        ("manager", "VARCHAR"),
        ("setup_date", "VARCHAR"),
        ("province", "VARCHAR"),
        ("city", "VARCHAR"),
        ("introduction", "TEXT"),
        ("main_business", "TEXT"),
        ("website", "VARCHAR"),
        ("employees", "FLOAT"),
        ("office", "TEXT"),
    ])
    _migrate_add_columns(engine, "daily_data", [
        ("return_3d", "FLOAT"),
        ("return_5d", "FLOAT"),
        ("return_13d", "FLOAT"),
        ("return_20d", "FLOAT"),
        ("return_60d", "FLOAT"),
        ("return_mid", "FLOAT"),
        ("vol_ma3", "FLOAT"),
        ("vol_ma5", "FLOAT"),
        ("vol_ma13", "FLOAT"),
        ("vol_ma30", "FLOAT"),
        ("is_30d_high", "FLOAT"),
        ("is_10d_high", "FLOAT"),
        ("ma5_slope3", "FLOAT"),
        ("close_above_ma5_5d", "FLOAT"),
        ("last_close_above_ma5", "FLOAT"),
        ("pattern_tags", "TEXT"),
    ])
    _migrate_add_columns(engine, "strategies", [
        ("setup_weight", "FLOAT DEFAULT 0"),
    ])
    _migrate_add_columns(engine, "scores", [
        ("setup_score", "FLOAT DEFAULT 0"),
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
            "news_weight": 0.0,
            "heat_weight": 0.40,
        },
        {
            "name": "trend",
            "display_name": "趋势策略",
            "technical_weight": 0.55,
            "capital_weight": 0.30,
            "fundamental_weight": 0.0,
            "news_weight": 0.0,
            "heat_weight": 0.15,
            "setup_weight": 0.0,
        },
        {
            "name": "setup",
            "display_name": "埋伏策略",
            "technical_weight": 0.0,
            "capital_weight": 0.0,
            "fundamental_weight": 0.0,
            "news_weight": 0.0,
            "heat_weight": 0.0,
            "setup_weight": 1.0,
        },
    ]
    for s in strategies:
        upsert(session, Strategy, s, ["name"])
    session.commit()
