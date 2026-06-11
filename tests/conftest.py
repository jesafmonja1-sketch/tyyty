import pytest
from sqlalchemy.orm import Session

from world_cup_intel.db import SessionLocal, build_engine, create_schema


@pytest.fixture()
def session(tmp_path) -> Session:
    engine = build_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    create_schema(engine)
    SessionLocal.configure(bind=engine)
    with SessionLocal() as db_session:
        yield db_session
