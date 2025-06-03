#models\user.py
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from . import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String, nullable=False)
    timezone = Column(String, nullable=True)

    categories = relationship("Category", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")
    monthly_metrics = relationship("MonthlyMetric", back_populates="user")