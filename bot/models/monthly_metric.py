# models/monthly_metric.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from . import Base


class MonthlyMetric(Base):
    __tablename__ = "monthly_metrics"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    year_month = Column(String, nullable=False, index=True)
    total_income = Column(Float, default=0.0)
    total_expense = Column(Float, default=0.0)
    avg_daily_expense = Column(Float, default=0.0)
    top_category = Column(String, nullable=True)
    top_category_pct = Column(Float, default=0.0)
    avg_usd = Column(Float, default=0.0)  # USD→UAH
    avg_eur = Column(Float, default=0.0)  # EUR→UAH

    user = relationship("User", back_populates="monthly_metrics")
