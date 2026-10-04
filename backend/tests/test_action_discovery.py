from __future__ import annotations

from datetime import UTC, date, datetime

from atlas.domain.action import (
    CapabilityCategory,
    CapabilityClaimStatus,
    CapabilityDirectness,
    CollaborationParticipant,
    RequiredCapability,
    RequirementLevel,
)
from atlas.domain.discovery import (
    AssetReuseStatus,
    AssetType,
    CapabilityEvidenceSignal,
    ResearchAsset,
    ResearchProgram,
)
from atlas.services.action_discovery import (
    assess_capability,
    generate_discovery_queries,
    potential_duplication,
    synthesize_collaboration,
)


def _signal(
    evidence_id: str,
    source_type: str,
    *,
    scope: str = "lab",
    explicit: bool = True,
    context: bool = True,
    model: bool = True,
    active: bool | None = True,
    year: int | None = 2025,
) -> CapabilityEvidenceSignal:
    return CapabilityEvidenceSignal(
        evidence_id=evidence_id,
        source_type=source_type,
        subject_scope=scope,
        explicitly_demonstrates=explicit,
        biological_context_match=context,
        model_system_match=model,
        active=active,
        publication_year=year,
        exact_support="The lab generated patient-derived iPSC neurons.",
        source_url=f"https://example.org/{evidence_id}",
    )


def _assess(*signals: CapabilityEvidenceSignal, subject_type: str = "laboratory"):
    return assess_capability(
        claim_id="claim:capability:1",
        subject_type=subject_type,
        subject_id="lab:1" if subject_type == "laboratory" else "researcher:1",
        capability_id="capability:ipsc-neurons",
        statement="The subject has demonstrated iPSC neuronal modeling.",
        signals=signals,
        today=date(2026, 10, 3),
    )


def test_lab_page_plus_publication_is_verified() -> None:
    claim = _assess(
        _signal("web:1", "official_lab_page"),
        _signal("pmid:1", "publication"),
    )
    assert claim.status is CapabilityClaimStatus.VERIFIED
    assert claim.directness is CapabilityDirectness.TEAM_LEVEL


def test_institution_core_is_not_transferred_to_researcher() -> None:
    claim = _assess(
        _signal("core:1", "institutional_page", scope="institution"),
        subject_type="researcher",
    )
    assert claim.status is CapabilityClaimStatus.PLAUSIBLE
    assert claim.directness is CapabilityDirectness.INSTITUTION_LEVEL
    assert claim.evidence_items == ()


def test_old_publication_without_current_activity_is_outdated() -> None:
    claim = _assess(
        _signal("pmid:old", "publication", active=False, year=2014),
    )
    assert claim.status is CapabilityClaimStatus.OUTDATED


def test_active_grant_is_strong_current_signal() -> None:
    claim = _assess(_signal("grant:1", "active_grant"))
    assert claim.status is CapabilityClaimStatus.SUPPORTED
    assert "active grant" in claim.rationale.lower()


def test_vague_gene_therapy_page_is_not_verified() -> None:
    claim = _assess(_signal("web:vague", "official_lab_page", explicit=False))
    assert claim.status is CapabilityClaimStatus.PLAUSIBLE


def test_program_overlap_is_only_potential_duplication() -> None:
    common = {
        "disease": ("SCAR16",),
        "gene": ("STUB1",),
        "mechanism": ("CHIP loss",),
        "therapeutic_modality": ("gene therapy",),
        "development_stage": "preclinical",
        "evidence": ("source:1",),
        "current_status": "active",
        "last_verified_at": datetime.now(UTC),
    }
    left = ResearchProgram(program_id="program:us", organization="A", geography=("US",), **common)
    right = ResearchProgram(
        program_id="program:cn", organization="B", geography=("China",), **common
    )
    assert potential_duplication(left, right) == (
        "POTENTIAL DUPLICATION / COORDINATION OPPORTUNITY"
    )


def test_context_mismatched_asset_requires_validation() -> None:
    asset = ResearchAsset(
        asset_id="asset:1",
        canonical_name="STUB1 fibroblast line",
        asset_type=AssetType.FIBROBLAST_LINE,
        disease_context=("SCAR16",),
        mechanism_context=("proteostasis",),
        model_context=("fibroblast",),
        availability="request from creator",
        evidence=("PMID:1",),
        source_url="https://example.org/asset",
        last_verified_at=datetime.now(UTC),
        reuse_status=AssetReuseStatus.REQUIRES_VALIDATION,
    )
    assert asset.reuse_status is AssetReuseStatus.REQUIRES_VALIDATION


def test_empty_search_does_not_claim_no_researcher_exists() -> None:
    claim = _assess()
    assert claim.status is CapabilityClaimStatus.UNVERIFIED
    assert "identified" in claim.rationale


def test_queries_are_capability_and_context_specific() -> None:
    capability = RequiredCapability(
        capability_id="capability:1",
        experiment_id="experiment:1",
        canonical_name="iPSC neuronal differentiation",
        description="directed neuronal differentiation",
        capability_category=CapabilityCategory.IPSC_NEURONAL_DIFFERENTIATION,
        required_or_optional=RequirementLevel.REQUIRED,
        reason_required="needed by experiment",
        mechanism_context="CHIP function",
        disease_context="SCAR16",
        model_context="human neurons",
        evidence_source="experiment:1#required_capabilities[0]",
        generated_by="test",
    )
    queries = generate_discovery_queries(
        (capability,),
        gene="STUB1",
        disease="SCAR16",
        mechanism_terms=("CHIP ubiquitin ligase",),
    )
    assert queries
    assert all(
        "STUB1" in item.query or "SCAR16" in item.query or "CHIP" in item.query
        for item in queries
    )
    assert any(item.query == '"STUB1" "iPSC neurons"' for item in queries)


def test_collaboration_exposes_missing_capability() -> None:
    supported = _assess(_signal("grant:1", "active_grant"))
    collaboration = synthesize_collaboration(
        collaboration_id="collaboration:1",
        experiment_id="experiment:1",
        knowledge_gap_id="gap:1",
        participants=(
            CollaborationParticipant(
                subject_type="laboratory",
                subject_id="lab:1",
                proposed_role="neuronal modeling",
                capability_claim_ids=(supported.claim_id,),
            ),
        ),
        capability_claims=(supported,),
        required_capability_ids=(supported.capability_id, "capability:assay"),
        provided_assets=("asset:ipsc",),
        rationale="Complementary expertise may address the experiment.",
        uncertainties=("Assay access is not verified.",),
        duplication_risk="not assessed",
        synergy="Model generation plus functional testing.",
        first_contact_target="lab:1",
        suggested_next_action="Ask the lab to confirm assay access.",
    )
    assert collaboration.status.value == "MISSING_CAPABILITY"
    assert collaboration.missing_capabilities == ("capability:assay",)
