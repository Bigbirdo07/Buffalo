#!/usr/bin/env python3
"""Record the reviewer's scientific decisions as append-only ScientificReview records.

These are decisions by the project's domain expert on classification questions the
deterministic pipeline could not settle. They are stored as review overlays: the
machine-produced value is preserved in ``original_value`` and the accepted value
in ``proposed_revision``, so no machine output is overwritten.

The reviewer is identified by role rather than by personal contact details.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from atlas.domain.reviews import (
    ReviewTargetType,
    ScientificReview,
    ScientificReviewStatus,
    apply_review,
)
from atlas.persistence.database import create_engine_for_url, create_schema
from atlas.persistence.repository import AtlasRepository

ROOT = Path(__file__).resolve().parents[1]
REFINEMENT = ROOT / "data" / "refinement" / "scar16_stub1_e3"
SOURCE_VERSION = "b923d18f1c962eeaecf9f1f908305b21a8f26904"
SOFTWARE_VERSION = "phase4-action-engine"
REVIEWER_NAME = "project domain reviewer"
REVIEWER_ROLE = "biologist; rare-disease mechanism and evidence appraisal"
# Fixed so the artifact is reproducible; the decisions were given on this date.
REVIEWED_AT = datetime(2026, 10, 3, tzinfo=UTC)


def build_reviews() -> tuple[ScientificReview, ...]:
    return (
        ScientificReview(
            review_id="review:scar16:ac4-allele-class-naming",
            target_type=ReviewTargetType.ATOMIC_CLAIM,
            target_id="ac4-interdomain-missense",
            reviewer_name=REVIEWER_NAME,
            reviewer_role=REVIEWER_ROLE,
            status=ScientificReviewStatus.APPROVED_WITH_MODIFICATION,
            original_value={
                "scope_class": "inter-domain missense",
                "statement_scope_class_as_generated": (
                    "inter-domain (coiled-coil) missense"
                ),
                "variant_scope": ["p.Lys145Gln", "p.Met211Ile"],
                "basis": (
                    "Coiled-coil terminology was taken from the source publications "
                    "(PMID:31619515 describes CC mutations)."
                ),
            },
            proposed_revision={
                "scope_class": "inter-domain/linker-region missense",
                "variant_scope": ["p.Lys145Gln", "p.Met211Ile"],
                "coiled_coil_terminology": (
                    "retained only as source-specific paper terminology, attributed to "
                    "the publication that uses it"
                ),
                "uniprot_claim": (
                    "none; UniProt Q9UNE7 annotates no coiled-coil feature, so no "
                    "UniProt-supported coiled-coil annotation may be asserted"
                ),
            },
            reviewed_at=REVIEWED_AT,
            comments=(
                "Use inter-domain/linker-region as the canonical classification for "
                "p.Lys145Gln and p.Met211Ile."
            ),
            scientific_rationale=(
                "UniProt Q9UNE7 annotates TPR repeats at 26-127 and the U-box at "
                "226-300 and carries no coiled-coil feature, so residues 145 and 211 "
                "fall in an unannotated linker region. Naming the class after a "
                "structural feature the reference proteome does not annotate would "
                "assert structure the evidence does not support. Paper terminology is "
                "preserved as attributed source wording."
            ),
            source_version=SOURCE_VERSION,
            software_version=SOFTWARE_VERSION,
        ),
        ScientificReview(
            review_id="review:scar16:n65s-effect-classification",
            target_type=ReviewTargetType.EVIDENCE_CLASSIFICATION,
            target_id="o07",
            reviewer_name=REVIEWER_NAME,
            reviewer_role=REVIEWER_ROLE,
            status=ScientificReviewStatus.APPROVED_WITH_MODIFICATION,
            original_value={
                "observation_ids": ["o07", "o09"],
                "variant": "p.Asn65Ser",
                "effect": "substrate_selective",
                "readout": "hsc70_ubiquitination",
                "basis": (
                    "Hsc70 was mono-ubiquitinated while CHIP self-ubiquitination was "
                    "retained (PMID:28396517, PMID:25258038)."
                ),
            },
            proposed_revision={
                "effect": "processivity_or_chain_elongation_defect",
                "substrate_selectivity_claim": (
                    "not asserted; requires comparative substrate experiments that "
                    "directly demonstrate selectivity between substrates"
                ),
                "evidence_required_to_upgrade": (
                    "side-by-side ubiquitination of two or more defined CHIP clients "
                    "under matched conditions"
                ),
            },
            reviewed_at=REVIEWED_AT,
            comments=(
                "Classify p.Asn65Ser as a processivity/chain-elongation defect rather "
                "than substrate_selective."
            ),
            scientific_rationale=(
                "Mono-ubiquitination of Hsc70 with retained self-ubiquitination shows "
                "impaired polyubiquitin chain elongation on that substrate. It does not "
                "compare substrates against one another, so it cannot establish "
                "selectivity between substrates. Selectivity requires a comparative "
                "substrate experiment."
            ),
            source_version=SOURCE_VERSION,
            software_version=SOFTWARE_VERSION,
        ),
        ScientificReview(
            review_id="review:scar16:sca48-entity-separation",
            target_type=ReviewTargetType.EVIDENCE_CLASSIFICATION,
            target_id="disease-entity-scope:SCAR16-vs-SCA48",
            reviewer_name=REVIEWER_NAME,
            reviewer_role=REVIEWER_ROLE,
            status=ScientificReviewStatus.APPROVED,
            original_value={
                "disease_scope": ["SCAR16"],
                "sca48_handling": (
                    "cross-entity; SUPPORTS/REFUTES downgraded to QUALIFIES and "
                    "directness set to INDIRECT"
                ),
                "affected_observations": ["o14", "o15", "o16"],
                "open_question": (
                    "DisMech describes SCAR16 and SCA48 as a clinical continuum and "
                    "PMID:34070858 reports biochemically indistinguishable defects, "
                    "which could argue for pooling the entities."
                ),
            },
            reviewed_at=REVIEWED_AT,
            comments=(
                "Retain SCA48 as a separate disease entity. Its evidence may qualify "
                "SCAR16 mechanism claims but remains INDIRECT/QUALIFIES."
            ),
            scientific_rationale=(
                "Shared STUB1 biology makes SCA48 evidence informative about the same "
                "protein, so it legitimately qualifies SCAR16 mechanism claims. It is "
                "not a test in the claimed entity, and the inheritance mode and allele "
                "spectrum differ, so it must not be promoted to direct SCAR16 evidence. "
                "The existing cross-entity downgrade is therefore correct as generated."
            ),
            source_version=SOURCE_VERSION,
            software_version=SOFTWARE_VERSION,
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=None, help="optional; also persist")
    parser.add_argument(
        "--output", type=Path, default=REFINEMENT / "scientific_reviews.json"
    )
    args = parser.parse_args()

    reviews = build_reviews()
    accepted = [item for item in (apply_review(review) for review in reviews) if item]
    payload = {
        "schema_version": "scientific-reviews-v1",
        "note": (
            "Append-only review overlays. The machine-produced value is preserved in "
            "original_value; an accepted interpretation never overwrites it."
        ),
        "reviews": [review.model_dump(mode="json") for review in reviews],
        "accepted_interpretations": [item.model_dump(mode="json") for item in accepted],
    }
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    persisted = 0
    if args.database_url:
        engine = create_engine_for_url(args.database_url)
        create_schema(engine)
        repository = AtlasRepository(engine)
        for review in reviews:
            repository.append_review(review)
            persisted += 1
        stored = {
            review.target_id: len(repository.reviews_for(review.target_id))
            for review in reviews
        }
    else:
        stored = {}

    print(
        json.dumps(
            {
                "output": str(args.output),
                "reviews": len(reviews),
                "statuses": [review.status.value for review in reviews],
                "accepted_interpretations": len(accepted),
                "persisted": persisted,
                "reviews_per_target": stored,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
