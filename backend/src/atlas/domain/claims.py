"""Atomic scientific claims and evidence-fit review results."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from atlas.domain.provenance import Provenance, ProvenanceKind


class ClaimType(StrEnum):
    CURATED = "curated"
    EXTRACTED = "extracted"
    INFERRED = "inferred"
    HYPOTHESIS = "hypothesis"


class RefinementStatus(StrEnum):
    UNREVIEWED = "UNREVIEWED"
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTEXT_DEPENDENT = "CONTEXT_DEPENDENT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONTRADICTED = "CONTRADICTED"


class EvidenceFit(StrEnum):
    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    QUALIFIES = "QUALIFIES"
    NEUTRAL = "NEUTRAL"
    UNRELATED = "UNRELATED"


class Directness(StrEnum):
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"
    BACKGROUND_ONLY = "BACKGROUND_ONLY"


class CausalSupport(StrEnum):
    CAUSAL = "CAUSAL"
    ASSOCIATIONAL = "ASSOCIATIONAL"
    NONE = "NONE"


class Claim(BaseModel):
    """An atomic, scoped relationship; never an untraceable prose conclusion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    subject: str
    predicate: str
    object: str
    normalized_statement: str
    original_statement: str
    claim_scope: str
    claim_type: ClaimType
    disease_context: str
    subtype_context: tuple[str, ...] = ()
    variant_context: tuple[str, ...] = ()
    protein_domain_context: tuple[str, ...] = ()
    species: tuple[str, ...] = ()
    tissue: tuple[str, ...] = ()
    cell_type: tuple[str, ...] = ()
    experimental_context: tuple[str, ...] = ()
    source_claim_origin: str
    extraction_method: str
    derived_from_claim_ids: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_reviewed_at: datetime | None = None
    refinement_status: RefinementStatus = RefinementStatus.UNREVIEWED
    status_rationale: str | None = None
    rationale_evidence_ids: tuple[str, ...] = ()
    provenance: Provenance

    @model_validator(mode="after")
    def status_requires_traceable_rationale(self) -> Claim:
        reviewed = self.refinement_status is not RefinementStatus.UNREVIEWED
        if reviewed and (not self.status_rationale or not self.rationale_evidence_ids):
            raise ValueError("reviewed claims require rationale and evidence IDs")
        expected = ProvenanceKind(self.claim_type.value.upper())
        if self.provenance.kind is not expected:
            raise ValueError("claim_type and provenance.kind must agree")
        return self


class EvidenceReview(BaseModel):
    """Strict output of an independent claim/source critic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    source_id: str
    supports: EvidenceFit
    directness: Directness
    paper_generated_finding: bool
    disease_match: bool
    gene_match: bool | None = None
    direction_match: bool | None = None
    species_match: bool
    tissue_match: bool | None = None
    cell_type_match: bool | None = None
    variant_match: bool | None = None
    causal_support: CausalSupport
    recommended_claim_scope: str
    limitations: tuple[str, ...]
    rationale: str

    @model_validator(mode="after")
    def reject_scientifically_inconsistent_fit(self) -> EvidenceReview:
        if not self.disease_match and self.supports is EvidenceFit.SUPPORTS:
            raise ValueError("a wrong-disease source cannot be classified SUPPORTS")
        if self.directness is Directness.BACKGROUND_ONLY and self.paper_generated_finding:
            raise ValueError("background-only text cannot be the paper's generated finding")
        if self.causal_support is CausalSupport.CAUSAL and self.supports in {
            EvidenceFit.NEUTRAL,
            EvidenceFit.UNRELATED,
        }:
            raise ValueError("neutral/unrelated evidence cannot establish causality")
        return self

