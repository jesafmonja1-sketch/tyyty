from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from world_cup_intel.schema import Base


def build_engine(database_url: str):
    engine = create_engine(database_url, future=True)
    if engine.url.drivername.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


SessionLocal = sessionmaker(expire_on_commit=False, future=True)


def create_schema(engine) -> None:
    Base.metadata.create_all(engine)
