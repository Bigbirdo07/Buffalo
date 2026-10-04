"""Consequential gaps and source-by-source search coverage."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CoverageStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    CHECKED = "CHECKED"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SearchSourceCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    status: CoverageStatus
    queries: tuple[str, ...] = ()
    checked_at: datetime | None = None
    result_count: int | None = Field(default=None, ge=0)
    error: str | None = None
    pages_checked: int = Field(default=0, ge=0)
    pagination_limit: int | None = Field(default=None, ge=1)
    languages: tuple[str, ...] = ()
    geographic_regions: tuple[str, ...] = ()
    cache_hits: int = Field(default=0, ge=0)
    snapshot_references: tuple[str, ...] = ()
    estimated_cost: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def failure_must_be_visible(self) -> SearchSourceCoverage:
        if self.status is CoverageStatus.FAILED and not self.error:
            raise ValueError("failed coverage requires an error message")
        if self.status is CoverageStatus.CHECKED and self.checked_at is None:
            raise ValueError("checked coverage requires checked_at")
        return self


class SearchCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    coverage_id: str
    sources: tuple[SearchSourceCoverage, ...]
    search_started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    search_completed_at: datetime | None = None
    scope: str = "scientific_evidence"
    language_limitations: tuple[str, ...] = ()
    geographic_limitations: tuple[str, ...] = ()
    interpretation_caveat: str = (
        "Absence in this search is not proof that relevant evidence does not exist."
    )


class GapType(StrEnum):
    UNSUPPORTED_CAUSAL_TRANSITION = "unsupported_causal_transition"
    ASSOCIATION_WITHOUT_CAUSAL_EVIDENCE = "association_without_causal_evidence"
    CONFLICTING_STUDIES = "conflicting_studies"
    UNTESTED_DISEASE_RELEVANT_CELL_TYPE = "untested_disease_relevant_cell_type"
    UNTESTED_VARIANT_CLASS = "untested_variant_class"
    SUBTYPE_UNCERTAINTY = "subtype_uncertainty"
    UNKNOWN_PROTEIN_DOMAIN_EFFECT = "unknown_protein_domain_effect"
    MODEL_WITHOUT_HUMAN_VALIDATION = "model_without_human_validation"
    HUMAN_ASSOCIATION_WITHOUT_MECHANISM = "human_association_without_mechanism"
    MISSING_REPLICATION = "missing_replication"
    MISSING_MODEL = "missing_model"
    MISSING_ASSAY = "missing_assay"
    SOURCE_DATA_ABSENCE = "source_data_absence"
    OTHER = "other"


class GapPriorityDimensions(BaseModel):
    """Named review dimensions; not a clinical or opaque aggregate score."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    causal_centrality: str
    downstream_dependence: str
    evidence_conflict: str
    translational_relevance: str
    experimental_tractability: str
    available_assets: str
    discriminates_competing_hypotheses: str


class KnowledgeGap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    gap_id: str
    question: str
    gap_type: GapType
    related_claims: tuple[str, ...]
    related_edges: tuple[str, ...]
    scope: str
    why_it_matters: str
    current_evidence_summary: str
    contradictory_evidence_summary: str
    search_coverage: SearchCoverage
    missing_evidence_type: tuple[str, ...]
    required_context: tuple[str, ...]
    priority_reason: GapPriorityDimensions
    resolvability: str
    proposed_discriminating_test: str | None = None
    status: str = "OPEN"


def pending_search_coverage(coverage_id: str) -> SearchCoverage:
    """Create the mandatory coverage scaffold without pretending sources ran."""
    sources = (
        "DisMech",
        "Monarch KG",
        "PubMed",
        "PMC",
        "ClinicalTrials.gov",
        "NIH RePORTER",
        "model organism source",
    )
    return SearchCoverage(
        coverage_id=coverage_id,
        sources=tuple(
            SearchSourceCoverage(source=source, status=CoverageStatus.NOT_STARTED)
            for source in sources
        ),
    )
