"""Versioned refinement-run records."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class RefinementRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    disease_id: str
    dismech_source_version: str
    monarch_data_date: str | None = None
    pubmed_retrieval_date: str | None = None
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    model_versions: dict[str, str] = Field(default_factory=dict)
    software_commit: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    parent_run_id: str | None = None

