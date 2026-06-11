from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from world_cup_intel.schema import Base


def build_engine(database_url: str):
    return create_engine(database_url, future=True)


SessionLocal = sessionmaker(expire_on_commit=False, future=True)


def create_schema(engine) -> None:
    Base.metadata.create_all(engine)
