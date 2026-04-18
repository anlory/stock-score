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
    return SessionLocal()

def upsert(session, model, data: dict, index_elements: list):
    stmt = sqlite_insert(model).values(**data)
    update_cols = {k: stmt.excluded[k] for k in data if k not in index_elements}
    stmt = stmt.on_conflict_do_update(index_elements=index_elements, set_=update_cols)
    session.execute(stmt)
