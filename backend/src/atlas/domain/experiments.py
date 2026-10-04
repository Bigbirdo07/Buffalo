"""Mechanistic hypotheses and falsifiable research proposals."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HypothesisStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNRESOLVED = "unresolved"
    WEAKLY_SUPPORTED = "weakly_supported"
    CONTRADICTED = "contradicted"


class MechanisticHypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis_id: str
    statement: str
    upstream_trigger: str
    proposed_mechanism: str
    downstream_consequence: str
    disease_context: str
    subtype_context: tuple[str, ...] = ()
    supporting_claims: tuple[str, ...] = ()
    contradictory_claims: tuple[str, ...] = ()
    alternative_hypotheses: tuple[str, ...] = ()
    status: HypothesisStatus = HypothesisStatus.UNRESOLVED
    upstream_status: str | None = None
    unresolved_assumptions: tuple[str, ...] = ()
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExperimentProposal(BaseModel):
    """A falsifiable research proposal; never clinical validation or advice."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_id: str
    knowledge_gap_id: str
    scientific_question: str
    hypothesis: str
    competing_hypothesis: str
    model_system: str
    sample_type: str
    patient_stratification: tuple[str, ...] = ()
    perturbation: str
    comparator: str
    controls: tuple[str, ...]
    readouts: tuple[str, ...]
    primary_endpoint: str
    secondary_endpoints: tuple[str, ...] = ()
    expected_result_if_supported: str
    expected_result_if_refuted: str
    confounders: tuple[str, ...]
    known_limitations: tuple[str, ...]
    required_assets: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    safety_or_ethics_flags: tuple[str, ...] = ()
    unjustified_interpretations: tuple[str, ...]
    human_review_required: bool = True
    label: str = "Research proposal requiring expert review."

    @model_validator(mode="after")
    def preserve_falsifiability_and_review(self) -> ExperimentProposal:
        if not self.expected_result_if_refuted.strip():
            raise ValueError("a weakening/refutation condition is required")
        if not self.controls:
            raise ValueError("at least one control is required")
        if not self.human_review_required:
            raise ValueError("experiment proposals always require human review")
        return self

