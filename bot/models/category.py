from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from . import Base

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # 'income' or 'expense'
    is_default = Column(Boolean, default=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # relationship back to user
    user = relationship("User", back_populates="categories")
    transactions = relationship("Transaction", back_populates="category")
