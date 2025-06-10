import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from bot.models import Base


@pytest.fixture(scope="module")
def engine():
    """
    Створює в пам’яті SQLite-движок, ініціалізує схему.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="function")
def session(engine):
    """
    Відкриває транзакцію перед тестом і відкочується після нього.
    """
    connection = engine.connect()
    trans = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    trans.rollback()
    connection.close()
