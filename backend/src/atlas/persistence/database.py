"""Database engine and explicit schema-version initialization."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from atlas.persistence.models import Base, SchemaVersionRecord

SCHEMA_VERSION = 1


def create_engine_for_url(database_url: str) -> Engine:
    return create_engine(database_url, future=True)


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        current = session.scalar(
            select(SchemaVersionRecord).order_by(SchemaVersionRecord.version.desc())
        )
        if current is None:
            session.add(SchemaVersionRecord(version=SCHEMA_VERSION))
            session.commit()
        elif current.version != SCHEMA_VERSION:
            raise RuntimeError(
                f"database schema is {current.version}; software requires {SCHEMA_VERSION}"
            )
