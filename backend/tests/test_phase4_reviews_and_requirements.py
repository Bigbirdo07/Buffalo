from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from atlas.domain.action import (
    CapabilityClaim,
    CapabilityClaimStatus,
    CapabilityDirectness,
    RequiredAssetType,
)
from atlas.domain.experiments import ExperimentProposal
from atlas.domain.reviews import (
    ReviewTargetType,
    ScientificReview,
    ScientificReviewStatus,
    apply_review,
)
from atlas.services.requirement_extraction import extract_experiment_requirements

ROOT = Path(__file__).resolve().parents[2]


def _experiment() -> ExperimentProposal:
    path = ROOT / "data/refinement/scar16_stub1_e3/experiment_proposal.json"
    return ExperimentProposal.model_validate(json.loads(path.read_text()))


def test_modified_review_preserves_machine_value() -> None:
    machine = {"status": "CONTEXT_DEPENDENT"}
    review = ScientificReview(
        review_id="review:1",
        target_type=ReviewTargetType.REFINED_EDGE,
        target_id="edge:1",
        reviewer_name="Dr Reviewer",
        reviewer_role="molecular geneticist",
        status=ScientificReviewStatus.APPROVED_WITH_MODIFICATION,
        original_value=machine,
        proposed_revision={"status": "CONTEXT_DEPENDENT", "scope": "substrate-specific"},
        comments="Bulk activity remains preserved.",
        scientific_rationale="The revision narrows the readout context.",
        reviewed_at=datetime.now(UTC),
        source_version="phase3:scar16",
        software_version="0.2.0",
    )

    accepted = apply_review(review)

    assert accepted is not None
    assert accepted.machine_value == machine
    assert accepted.accepted_value != machine
    assert review.original_value == machine


def test_modified_review_requires_revision() -> None:
    with pytest.raises(ValidationError, match="proposed_revision"):
        ScientificReview(
            review_id="review:bad",
            target_type=ReviewTargetType.KNOWLEDGE_GAP,
            target_id="gap:1",
            reviewer_id="reviewer:1",
            reviewer_role="scientist",
            status=ScientificReviewStatus.APPROVED_WITH_MODIFICATION,
            original_value={"question": "original"},
            reviewed_at=datetime.now(UTC),
            source_version="1",
            software_version="0.2.0",
        )


def test_scar16_requirements_are_derived_from_explicit_fields() -> None:
    experiment = _experiment()

    capabilities, assets = extract_experiment_requirements(experiment)

    categories = {capability.capability_category.value for capability in capabilities}
    assert "crispr_editing" in categories
    assert "isogenic_line_generation" in categories
    assert "ipsc_neuronal_differentiation" in categories
    assert "ubiquitination_assay" in categories
    assert "proteomics" in categories
    assert "protein_biochemistry" in categories
    assert "statistical_analysis" in categories
    assert all(item.evidence_source.startswith(experiment.experiment_id) for item in capabilities)
    assert {asset.asset_type for asset in assets} >= {
        RequiredAssetType.PATIENT_DERIVED_IPSC,
        RequiredAssetType.ANTIBODY,
        RequiredAssetType.MASS_SPECTROMETRY_ACCESS,
    }
    assert all(asset.human_review_status is ScientificReviewStatus.PENDING for asset in assets)


def test_requirement_ids_are_deterministic() -> None:
    experiment = _experiment()
    first = extract_experiment_requirements(experiment)
    second = extract_experiment_requirements(experiment)
    assert first == second


def test_institution_core_does_not_verify_personal_capability() -> None:
    with pytest.raises(ValidationError, match="institution infrastructure"):
        CapabilityClaim(
            claim_id="capability-claim:1",
            subject_type="researcher",
            subject_id="researcher:1",
            capability_id="required-capability:1",
            statement="The researcher can generate iPSC neurons.",
            evidence_items=("core-page:1", "institution-page:2"),
            evidence_source_types=("institutional_page", "core_page"),
            directness=CapabilityDirectness.INSTITUTION_LEVEL,
            recency="current",
            corroboration_count=2,
            status=CapabilityClaimStatus.VERIFIED,
            rationale="Only the institution core is evidenced.",
            last_checked=date.today(),
        )
