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
    chairman = Column(String)
    manager = Column(String)
    setup_date = Column(String)
    province = Column(String)
    city = Column(String)
    introduction = Column(Text)
    main_business = Column(Text)
    website = Column(String)
    employees = Column(Float)
    office = Column(Text)
    # --- quote fields (from Tencent) ---
    total_mv = Column(Float)                       # 总市值(亿)
    float_mv = Column(Float)                       # 流通市值(亿)
    pe = Column(Float)                             # 市盈率
    pb = Column(Float)                             # 市净率
    profile_updated_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
