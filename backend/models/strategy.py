from sqlalchemy import Column, String, Float
from backend.models.stock import Base

class Strategy(Base):
    __tablename__ = "strategies"
    name = Column(String, primary_key=True)
    display_name = Column(String)
    technical_weight = Column(Float)
    capital_weight = Column(Float)
    fundamental_weight = Column(Float)
    news_weight = Column(Float)
    heat_weight = Column(Float)
