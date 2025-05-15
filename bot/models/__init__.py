from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from utils.config import DATABASE_URL

# Base class for all ORM models
Base = declarative_base()

# Import all models so that SQLAlchemy knows about them when creating tables
from .user import User
from .category import Category
from .transaction import Transaction
# Future models: BudgetLimit, etc.


def init_db(database_url: str):
    """
    Initialize the database connection and create tables for all registered ORM models.
    """
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    # Create all tables defined by subclasses of Base
    Base.metadata.create_all(engine)
    return engine

# SQLAlchemy session factory
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)