"""Append-only human review records for scientific and action outputs."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReviewTargetType(StrEnum):
    ATOMIC_CLAIM = "ATOMIC_CLAIM"
    EVIDENCE_CLASSIFICATION = "EVIDENCE_CLASSIFICATION"
    REFINED_EDGE = "REFINED_EDGE"
    KNOWLEDGE_GAP = "KNOWLEDGE_GAP"
    EXPERIMENT_PROPOSAL = "EXPERIMENT_PROPOSAL"
    REQUIRED_CAPABILITY = "REQUIRED_CAPABILITY"
    REQUIRED_ASSET = "REQUIRED_ASSET"
    CAPABILITY_MATCH = "CAPABILITY_MATCH"
    COLLABORATION_PROPOSAL = "COLLABORATION_PROPOSAL"
    ENTITY_RESOLUTION = "ENTITY_RESOLUTION"


class ScientificReviewStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    APPROVED_WITH_MODIFICATION = "APPROVED_WITH_MODIFICATION"
    REJECTED = "REJECTED"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"


class ScientificReview(BaseModel):
    """A versioned review overlay; it never mutates its target object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    review_id: str
    target_type: ReviewTargetType
    target_id: str
    reviewer_name: str | None = None
    reviewer_id: str | None = None
    reviewer_role: str
    status: ScientificReviewStatus = ScientificReviewStatus.PENDING
    original_value: dict[str, Any]
    proposed_revision: dict[str, Any] | None = None
    comments: str = ""
    scientific_rationale: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reviewed_at: datetime | None = None
    source_version: str
    software_version: str
    model_run_id: str | None = None

    @model_validator(mode="after")
    def enforce_review_lifecycle(self) -> ScientificReview:
        if not (self.reviewer_name or self.reviewer_id):
            raise ValueError("a reviewer_name or reviewer_id is required")
        if self.status is ScientificReviewStatus.PENDING:
            if self.reviewed_at is not None:
                raise ValueError("pending reviews cannot have reviewed_at")
        elif self.reviewed_at is None:
            raise ValueError("completed reviews require reviewed_at")
        if (
            self.status is ScientificReviewStatus.APPROVED_WITH_MODIFICATION
            and self.proposed_revision is None
        ):
            raise ValueError("modified approval requires proposed_revision")
        if self.status is ScientificReviewStatus.REJECTED and not self.scientific_rationale:
            raise ValueError("rejection requires scientific_rationale")
        return self


class AcceptedInterpretation(BaseModel):
    """A derived pointer that preserves both machine output and review decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_type: ReviewTargetType
    target_id: str
    machine_value: dict[str, Any]
    accepted_value: dict[str, Any]
    review_id: str
    derived_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def apply_review(review: ScientificReview) -> AcceptedInterpretation | None:
    """Derive an accepted view without modifying the machine-produced target."""
    if review.status not in {
        ScientificReviewStatus.APPROVED,
        ScientificReviewStatus.APPROVED_WITH_MODIFICATION,
    }:
        return None
    accepted = review.original_value
    if review.status is ScientificReviewStatus.APPROVED_WITH_MODIFICATION:
        assert review.proposed_revision is not None
        accepted = review.proposed_revision
    return AcceptedInterpretation(
        target_type=review.target_type,
        target_id=review.target_id,
        machine_value=review.original_value,
        accepted_value=accepted,
        review_id=review.review_id,
    )
