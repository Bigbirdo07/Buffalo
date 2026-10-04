"""Records produced by refining one upstream mechanism edge.

Upstream data (DisMech claims/evidence) is never modified. Everything here is a
new object that points back to upstream IDs via ``derived_from`` fields.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from atlas.domain.claims import Claim, EvidenceReview, RefinementStatus
from atlas.domain.evidence import CitationVerification, ContextAnnotation
from atlas.domain.gaps import SearchCoverage


class EffectDirection(StrEnum):
    ABOLISHED = "abolished"
    DECREASED = "decreased"
    PROCESSIVITY_DEFECT = "processivity_defect"
    SUBSTRATE_SELECTIVE = "substrate_selective"
    PARTIALLY_RETAINED = "partially_retained"
    UNCHANGED = "unchanged"
    INCREASED = "increased"


class FindingOrigin(StrEnum):
    PRIMARY_RESULT = "PRIMARY_RESULT"
    BACKGROUND_CITATION = "BACKGROUND_CITATION"
    REVIEW_SYNTHESIS = "REVIEW_SYNTHESIS"


class AtomicClaimSpec(BaseModel):
    """Machine-checkable scope of one atomic claim.

    ``variant_scope`` lists the alleles the claim covers; ``scope_class`` names the
    allele class (e.g. a protein domain) so that a class-level finding about the
    same class can be matched without pretending it names each allele.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    statement: str
    gene: str
    disease_scope: tuple[str, ...]
    variant_scope: tuple[str, ...]
    scope_class: str
    # Readouts that count as this capability at all (plan-wide).
    readout_family: tuple[str, ...]
    # Readouts that bear on *this* claim specifically. Sub-step claims ("fusion is
    # blocked" versus "autolysosome formation is impaired") are otherwise separated
    # only by how a human assigned observations to them, with nothing checkable.
    # Empty falls back to readout_family.
    readout_scope: tuple[str, ...] = ()
    expected_effect: tuple[EffectDirection, ...]
    species_scope: tuple[str, ...] = ("Homo sapiens",)
    # Cell type is a scoping axis in its own right, not part of the allele string.
    # SCAR16's claims scoped by allele and disease entity; SCAR20's scope by cell
    # type and sub-process, and conflating cell type into variant_scope made two
    # claims resting on identical evidence disagree purely on string spelling.
    # Empty means the claim is not cell-type scoped.
    cell_type_scope: tuple[str, ...] = ()


class EvidenceObservation(BaseModel):
    """One experiment-level finding with its context, extracted from a source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str
    evidence_id: str
    # Canonical publication identity, used for independence counting so one paper
    # cited in two upstream forms is not mistaken for two independent sources.
    source_identifier: str
    # What upstream actually wrote, retained for provenance.
    upstream_reference_form: str | None = None
    claim_ids: tuple[str, ...]
    gene: str
    disease_entity: str
    variants: tuple[str, ...]
    variant_class: str | None = None
    readout: str
    effect: EffectDirection
    origin: FindingOrigin
    species: str
    cell_types: tuple[str, ...] = ()
    experimental_system: str
    support_span: str
    source_location: str
    context: tuple[ContextAnnotation, ...]
    extraction_note: str | None = None

    @model_validator(mode="after")
    def class_or_alleles(self) -> EvidenceObservation:
        if not self.variants and not self.variant_class:
            raise ValueError("an observation must name alleles or an allele class")
        return self


class AtomicClaimSynthesis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim: Claim
    status: RefinementStatus
    direct_supporting: tuple[str, ...]
    direct_refuting: tuple[str, ...]
    direct_qualifying: tuple[str, ...]
    indirect: tuple[str, ...]
    background_only: tuple[str, ...]
    rule_applied: str
    rationale: str


class EdgeRefinement(BaseModel):
    """Complete, replayable output of one edge refinement run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    upstream_claim: Claim
    upstream_edge_id: str
    upstream_evidence_ids: tuple[str, ...]
    upstream_context_evidence_ids: tuple[str, ...]
    citation_checks: tuple[CitationVerification, ...]
    observations: tuple[EvidenceObservation, ...]
    reviews: tuple[EvidenceReview, ...]
    atomic: tuple[AtomicClaimSynthesis, ...]
    edge_status: RefinementStatus
    edge_rule_applied: str
    edge_rationale: str
    recommended_scope: str
    search_coverage: SearchCoverage
