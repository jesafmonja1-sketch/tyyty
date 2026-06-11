import pytest
from sqlalchemy.orm import Session, sessionmaker

from world_cup_intel.db import build_engine, create_schema


@pytest.fixture()
def session(tmp_path) -> Session:
    engine = build_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    create_schema(engine)
    local_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with local_session() as db_session:
        yield db_session
