"""SQLAlchemy tables; Postgres is canonical and SQLite supports isolated tests."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class SchemaVersionRecord(Base):
    __tablename__ = "atlas_schema_version"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ArtifactRecord(Base):
    """Lossless canonical payload for any versioned domain object."""

    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("object_id", "source_version", name="uq_artifact_object_version"),
        Index("ix_artifacts_type_status", "object_type", "status"),
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_version: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ReviewRecord(Base):
    __tablename__ = "scientific_reviews"
    __table_args__ = (Index("ix_reviews_target", "target_type", "target_id"),)

    review_id: Mapped[str] = mapped_column(String(512), primary_key=True)
    target_type: Mapped[str] = mapped_column(String(128), nullable=False)
    target_id: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(128), nullable=False)
    source_version: Mapped[str] = mapped_column(String(256), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LineageRecord(Base):
    __tablename__ = "lineage"
    __table_args__ = (
        UniqueConstraint(
            "parent_id",
            "child_id",
            "relationship",
            name="uq_lineage_edge",
        ),
        Index("ix_lineage_child", "child_id"),
    )

    lineage_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    child_id: Mapped[str] = mapped_column(String(512), nullable=False)
    relationship: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class WebSnapshotRecord(Base):
    __tablename__ = "web_snapshots"
    __table_args__ = (UniqueConstraint("url", "content_hash", name="uq_snapshot_url_hash"),)

    snapshot_id: Mapped[str] = mapped_column(String(512), primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_reference: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(128), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SearchRunRecord(Base):
    __tablename__ = "search_runs"

    search_run_id: Mapped[str] = mapped_column(String(512), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(128), nullable=False)
    coverage_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
