from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from atlas.domain.experiments import ExperimentProposal
from atlas.domain.reviews import ReviewTargetType, ScientificReview, ScientificReviewStatus
from atlas.persistence import AtlasRepository, create_engine_for_url, create_schema

ROOT = Path(__file__).resolve().parents[2]


def _experiment() -> ExperimentProposal:
    path = ROOT / "data/refinement/scar16_stub1_e3/experiment_proposal.json"
    return ExperimentProposal.model_validate(json.loads(path.read_text()))


def _repository() -> AtlasRepository:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    return AtlasRepository(engine)


def test_experiment_round_trips_losslessly() -> None:
    repository = _repository()
    experiment = _experiment()
    repository.save_artifact(
        experiment,
        object_id=experiment.experiment_id,
        source_version="phase3:scar16",
        status="REQUIRES_EXPERT_REVIEW",
    )

    loaded = repository.load_artifact(
        ExperimentProposal,
        object_id=experiment.experiment_id,
        source_version="phase3:scar16",
    )

    assert loaded == experiment


def test_immutable_object_version_rejects_changed_payload() -> None:
    repository = _repository()
    experiment = _experiment()
    repository.save_artifact(
        experiment,
        object_id=experiment.experiment_id,
        source_version="phase3:scar16",
    )
    changed = experiment.model_copy(update={"scientific_question": "Changed after persistence"})

    with pytest.raises(ValueError, match="immutable artifact conflict"):
        repository.save_artifact(
            changed,
            object_id=experiment.experiment_id,
            source_version="phase3:scar16",
        )


def test_reviews_append_and_do_not_replace_artifact() -> None:
    repository = _repository()
    experiment = _experiment()
    repository.save_artifact(
        experiment,
        object_id=experiment.experiment_id,
        source_version="phase3:scar16",
    )
    review = ScientificReview(
        review_id="review:experiment:1",
        target_type=ReviewTargetType.EXPERIMENT_PROPOSAL,
        target_id=experiment.experiment_id,
        reviewer_id="reviewer:scientist:1",
        reviewer_role="cell biologist",
        status=ScientificReviewStatus.APPROVED,
        original_value=experiment.model_dump(mode="json"),
        comments="The controls and refutation criteria are adequate.",
        scientific_rationale="The design distinguishes the competing hypotheses.",
        reviewed_at=datetime.now(UTC),
        source_version="phase3:scar16",
        software_version="0.2.0",
    )

    repository.append_review(review)

    assert repository.reviews_for(experiment.experiment_id) == (review,)
    loaded = repository.load_artifact(
        ExperimentProposal,
        object_id=experiment.experiment_id,
        source_version="phase3:scar16",
    )
    assert loaded == experiment
    with pytest.raises(ValueError, match="append-only"):
        repository.append_review(review)


def test_lineage_keeps_evidence_references() -> None:
    repository = _repository()
    repository.add_lineage(
        parent_id="experiment:1",
        child_id="required-capability:1",
        relationship="REQUIRES",
        evidence_ids=("experiment:1#required_capabilities[0]",),
    )
    assert repository.lineage_to("required-capability:1") == (
        (
            "experiment:1",
            "REQUIRES",
            ("experiment:1#required_capabilities[0]",),
        ),
    )
