from sqlalchemy import Column, String, Float
from backend.models.stock import Base

class Score(Base):
    __tablename__ = "scores"
    code = Column(String, primary_key=True)
    date = Column(String, primary_key=True)
    strategy = Column(String, primary_key=True)
    technical_score = Column(Float, default=0)
    capital_score = Column(Float, default=0)
    fundamental_score = Column(Float, default=0)
    news_score = Column(Float, default=0)
    heat_score = Column(Float, default=0)
    total_score = Column(Float, default=0)
