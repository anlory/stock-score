from sqlalchemy import Column, String, Boolean, DateTime, Float, Text
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
    # --- profile fields ---
    business = Column(Text)
    industry = Column(String)
    concepts = Column(Text, default="[]")          # JSON string
    total_share = Column(Float)                    # 亿股
    float_share = Column(Float)                    # 亿股
    list_date = Column(String)                     # YYYY-MM-DD
    profile_updated_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
