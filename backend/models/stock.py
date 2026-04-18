from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Stock(Base):
    __tablename__ = "stocks"
    code = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    market = Column(String)
    is_watchlist = Column(Boolean, default=False)
    index_tags = Column(String, default="[]")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
