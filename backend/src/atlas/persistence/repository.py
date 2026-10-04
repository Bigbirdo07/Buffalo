"""Lossless artifact, review, and lineage persistence operations."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import TypeVar

from pydantic import BaseModel
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from atlas.domain.reviews import ScientificReview
from atlas.persistence.models import ArtifactRecord, LineageRecord, ReviewRecord

ModelT = TypeVar("ModelT", bound=BaseModel)


def _canonical_payload(model: BaseModel) -> tuple[dict[str, object], str]:
    serialized = model.model_dump_json(exclude_none=False)
    payload = json.loads(serialized)
    if not isinstance(payload, dict):
        raise TypeError("domain models must serialize to JSON objects")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return payload, sha256(canonical).hexdigest()


class AtlasRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def save_artifact(
        self,
        model: BaseModel,
        *,
        object_id: str,
        source_version: str,
        status: str | None = None,
    ) -> ArtifactRecord:
        """Store an artifact version idempotently.

        The read-then-insert pair is not atomic, so concurrent writers can both
        pass the existence check. The unique constraint on
        ``(object_id, source_version)`` is the real guarantee, and losing that
        race is expected rather than exceptional: it is resolved by re-reading
        the committed row. Identical content therefore stays idempotent under
        concurrency, and only genuinely different content raises.
        """
        payload, content_hash = _canonical_payload(model)

        def _reconcile(session: Session) -> ArtifactRecord:
            committed = session.scalar(
                select(ArtifactRecord).where(
                    ArtifactRecord.object_id == object_id,
                    ArtifactRecord.source_version == source_version,
                )
            )
            if committed is None:  # pragma: no cover - constraint implies a row exists
                raise ValueError(
                    "artifact insert conflicted but no committed row was found for "
                    f"{object_id!r} at version {source_version!r}"
                )
            if committed.content_hash != content_hash:
                raise ValueError(
                    "immutable artifact conflict: object/version already has different content"
                )
            return committed

        with Session(self.engine) as session:
            existing = session.scalar(
                select(ArtifactRecord).where(
                    ArtifactRecord.object_id == object_id,
                    ArtifactRecord.source_version == source_version,
                )
            )
            if existing is not None:
                if existing.content_hash != content_hash:
                    raise ValueError(
                        "immutable artifact conflict: object/version already has different content"
                    )
                return existing
            record = ArtifactRecord(
                object_id=object_id,
                object_type=model.__class__.__name__,
                source_version=source_version,
                status=status,
                content_hash=content_hash,
                payload=payload,
            )
            session.add(record)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return _reconcile(session)
            session.refresh(record)
            return record

    def load_artifact(
        self,
        model_type: type[ModelT],
        *,
        object_id: str,
        source_version: str,
    ) -> ModelT | None:
        with Session(self.engine) as session:
            record = session.scalar(
                select(ArtifactRecord).where(
                    ArtifactRecord.object_id == object_id,
                    ArtifactRecord.source_version == source_version,
                )
            )
            if record is None:
                return None
            return model_type.model_validate(record.payload)

    def append_review(self, review: ScientificReview) -> None:
        payload, _ = _canonical_payload(review)
        with Session(self.engine) as session:
            session.add(
                ReviewRecord(
                    review_id=review.review_id,
                    target_type=review.target_type.value,
                    target_id=review.target_id,
                    status=review.status.value,
                    source_version=review.source_version,
                    payload=payload,
                )
            )
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ValueError("reviews are append-only; review_id already exists") from exc

    def reviews_for(self, target_id: str) -> tuple[ScientificReview, ...]:
        with Session(self.engine) as session:
            records = session.scalars(
                select(ReviewRecord)
                .where(ReviewRecord.target_id == target_id)
                .order_by(ReviewRecord.created_at)
            ).all()
            return tuple(ScientificReview.model_validate(record.payload) for record in records)

    def add_lineage(
        self,
        *,
        parent_id: str,
        child_id: str,
        relationship: str,
        evidence_ids: tuple[str, ...] = (),
    ) -> None:
        with Session(self.engine) as session:
            session.add(
                LineageRecord(
                    parent_id=parent_id,
                    child_id=child_id,
                    relationship=relationship,
                    evidence_ids=list(evidence_ids),
                )
            )
            try:
                session.commit()
            except IntegrityError:
                session.rollback()

    def lineage_to(self, child_id: str) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
        with Session(self.engine) as session:
            records = session.scalars(
                select(LineageRecord)
                .where(LineageRecord.child_id == child_id)
                .order_by(LineageRecord.lineage_id)
            ).all()
            return tuple(
                (record.parent_id, record.relationship, tuple(record.evidence_ids))
                for record in records
            )
