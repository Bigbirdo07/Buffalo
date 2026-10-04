"""Provenance records used to reconstruct scientific outputs."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProvenanceKind(StrEnum):
    CURATED = "CURATED"
    EXTRACTED = "EXTRACTED"
    INFERRED = "INFERRED"
    HYPOTHESIS = "HYPOTHESIS"


class SourceSnapshot(BaseModel):
    """Immutable metadata for bytes received from an upstream source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_name: str
    source_locator: str
    source_version: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    media_type: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def from_bytes(
        cls,
        *,
        source_name: str,
        source_locator: str,
        source_version: str,
        media_type: str,
        content: bytes,
    ) -> SourceSnapshot:
        return cls(
            source_name=source_name,
            source_locator=source_locator,
            source_version=source_version,
            media_type=media_type,
            sha256=sha256(content).hexdigest(),
        )


class Provenance(BaseModel):
    """How an internal object was produced without hidden conversation state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ProvenanceKind
    source_name: str
    source_version: str
    source_object_path: str
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    extraction_method: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_payload: dict[str, Any] = Field(default_factory=dict)


class ModelInvocation(BaseModel):
    """Reproducible metadata for a structured scientific model call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    invocation_id: str
    provider: str
    model: str
    prompt_template_version: str
    response_schema_version: str
    invoked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    input_evidence_ids: tuple[str, ...] = ()
    output_object_ids: tuple[str, ...] = ()

