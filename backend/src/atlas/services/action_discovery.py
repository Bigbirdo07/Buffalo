"""Requirement-driven query generation and conservative action synthesis."""

from __future__ import annotations

from datetime import date, datetime
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict

from atlas.domain.action import (
    ActionabilityStatus,
    CapabilityCategory,
    CapabilityClaim,
    CapabilityClaimStatus,
    CapabilityDirectness,
    CollaborationOpportunity,
    CollaborationParticipant,
    RequiredCapability,
)
from atlas.domain.discovery import CapabilityEvidenceSignal, ResearchProgram


class DiscoveryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query_id: str
    capability_id: str
    source: str
    query: str
    rationale: str


_CATEGORY_TERMS: dict[CapabilityCategory, tuple[str, ...]] = {
    CapabilityCategory.CELL_CULTURE: ("iPSC", "patient-derived cells"),
    CapabilityCategory.CRISPR_EDITING: ("CRISPR", "genome editing"),
    CapabilityCategory.ISOGENIC_LINE_GENERATION: ("isogenic", "knock-in"),
    CapabilityCategory.IPSC_NEURONAL_DIFFERENTIATION: (
        "iPSC neurons",
        "cerebellar neuron model",
    ),
    CapabilityCategory.UBIQUITINATION_ASSAY: (
        "ubiquitin ligase assay",
        "substrate ubiquitination",
    ),
    CapabilityCategory.PROTEOMICS: ("diGly proteomics", "ubiquitinome"),
    CapabilityCategory.PROTEIN_BIOCHEMISTRY: (
        "protein thermal stability",
        "co-immunoprecipitation",
    ),
    CapabilityCategory.STATISTICAL_ANALYSIS: ("clone-level random effects",),
}


def generate_discovery_queries(
    capabilities: tuple[RequiredCapability, ...],
    *,
    gene: str,
    disease: str,
    mechanism_terms: tuple[str, ...],
    sources: tuple[str, ...] = ("PubMed", "NIH RePORTER", "institutional_web"),
) -> tuple[DiscoveryQuery, ...]:
    """Create narrow, auditable queries from experiment requirements."""
    result: list[DiscoveryQuery] = []
    seen: set[tuple[str, str]] = set()
    contexts = (gene, disease, *mechanism_terms)
    for capability in capabilities:
        terms = _CATEGORY_TERMS.get(
            capability.capability_category,
            (capability.canonical_name,),
        )
        for term in terms:
            for context in contexts:
                query = f'"{context}" "{term}"'
                for source in sources:
                    key = (source, query)
                    if key in seen:
                        continue
                    seen.add(key)
                    stable_key = f"{capability.capability_id}|{source}|{query}"
                    result.append(
                        DiscoveryQuery(
                            query_id=(
                                "discovery-query:"
                                f"{uuid5(NAMESPACE_URL, stable_key)}"
                            ),
                            capability_id=capability.capability_id,
                            source=source,
                            query=query,
                            rationale=(
                                f"Tests evidence for {capability.canonical_name} in the "
                                f"specific context {context}."
                            ),
                        )
                    )
    return tuple(result)


def assess_capability(
    *,
    claim_id: str,
    subject_type: str,
    subject_id: str,
    capability_id: str,
    statement: str,
    signals: tuple[CapabilityEvidenceSignal, ...],
    today: date,
) -> CapabilityClaim:
    """Apply explicit evidence-strength rules without an opaque score."""
    personal = subject_type == "researcher"
    relevant = tuple(
        signal
        for signal in signals
        if signal.explicitly_demonstrates
        and signal.biological_context_match
        and signal.model_system_match
        and not (personal and signal.subject_scope == "institution")
    )
    current = tuple(
        signal
        for signal in relevant
        if signal.active is True
        or signal.publication_year is None
        or signal.publication_year >= today.year - 5
    )
    source_types = tuple(dict.fromkeys(signal.source_type for signal in relevant))
    status = CapabilityClaimStatus.UNVERIFIED
    rationale = "No direct, context-matched evidence was identified for this subject."
    if relevant and not current:
        status = CapabilityClaimStatus.OUTDATED
        rationale = "Only historical evidence older than five years was identified."
    elif len(current) >= 2 and len({signal.source_type for signal in current}) >= 2:
        status = CapabilityClaimStatus.VERIFIED
        rationale = "Two current, context-matched source types directly demonstrate the capability."
    elif any(signal.source_type == "active_grant" for signal in current):
        status = CapabilityClaimStatus.SUPPORTED
        rationale = "An active grant directly supports current, context-matched capability."
    elif current:
        status = CapabilityClaimStatus.SUPPORTED
        rationale = (
            "Current direct evidence supports the capability but lacks "
            "cross-source corroboration."
        )
    elif signals:
        status = CapabilityClaimStatus.PLAUSIBLE
        rationale = (
            "Evidence exists, but its scope or experimental context does not directly match."
        )

    scopes = {signal.subject_scope for signal in relevant}
    if scopes == {"individual"}:
        directness = CapabilityDirectness.DIRECT
    elif "lab" in scopes or "team" in scopes:
        directness = CapabilityDirectness.TEAM_LEVEL
    elif scopes == {"institution"} or (not relevant and signals):
        directness = CapabilityDirectness.INSTITUTION_LEVEL
    else:
        directness = CapabilityDirectness.INDIRECT

    return CapabilityClaim(
        claim_id=claim_id,
        subject_type=subject_type,
        subject_id=subject_id,
        capability_id=capability_id,
        statement=statement,
        evidence_items=tuple(signal.evidence_id for signal in relevant),
        evidence_source_types=source_types,
        directness=directness,
        recency="current" if current else "historical_or_unknown",
        corroboration_count=len(current),
        status=status,
        rationale=rationale,
        last_checked=today,
    )


def potential_duplication(left: ResearchProgram, right: ResearchProgram) -> str:
    """Qualify overlap without asserting that independent programs duplicate work."""
    shared_disease = set(left.disease) & set(right.disease)
    shared_gene = set(left.gene) & set(right.gene)
    shared_modality = set(left.therapeutic_modality) & set(right.therapeutic_modality)
    if shared_disease and shared_gene and shared_modality:
        return "POTENTIAL DUPLICATION / COORDINATION OPPORTUNITY"
    return "NO SPECIFIC OVERLAP IDENTIFIED"


def synthesize_collaboration(
    *,
    collaboration_id: str,
    experiment_id: str,
    knowledge_gap_id: str,
    participants: tuple[CollaborationParticipant, ...],
    capability_claims: tuple[CapabilityClaim, ...],
    required_capability_ids: tuple[str, ...],
    provided_assets: tuple[str, ...],
    rationale: str,
    uncertainties: tuple[str, ...],
    duplication_risk: str,
    synergy: str,
    first_contact_target: str | None,
    suggested_next_action: str,
    created_at: datetime | None = None,
) -> CollaborationOpportunity:
    """Synthesize an opportunity conservatively.

    ``created_at`` may be pinned to the evidence as-of instant so that a bundle
    rebuilt from the same cache is byte-identical; left unset, the record stamps
    itself with the current time.
    """
    usable_claims = tuple(
        claim
        for claim in capability_claims
        if claim.status in {CapabilityClaimStatus.VERIFIED, CapabilityClaimStatus.SUPPORTED}
    )
    provided = tuple(dict.fromkeys(claim.capability_id for claim in usable_claims))
    missing = tuple(item for item in required_capability_ids if item not in provided)
    if missing:
        status = ActionabilityStatus.MISSING_CAPABILITY
    elif not provided_assets:
        status = ActionabilityStatus.MISSING_ASSET
    elif not first_contact_target:
        status = ActionabilityStatus.CONTACT_UNVERIFIED
    else:
        status = ActionabilityStatus.READY_FOR_EXPERT_REVIEW
    return CollaborationOpportunity(
        collaboration_id=collaboration_id,
        experiment_id=experiment_id,
        knowledge_gap_id=knowledge_gap_id,
        participants=participants,
        provided_capabilities=provided,
        provided_assets=provided_assets,
        missing_capabilities=missing,
        rationale=rationale,
        evidence=tuple(
            evidence_id for claim in usable_claims for evidence_id in claim.evidence_items
        ),
        uncertainties=uncertainties,
        duplication_risk=duplication_risk,
        synergy=synergy,
        proposed_roles=tuple(participant.proposed_role for participant in participants),
        first_contact_target=first_contact_target,
        suggested_next_action=suggested_next_action,
        status=status,
        **({} if created_at is None else {"created_at": created_at}),
    )
