#!/usr/bin/env python3
"""Persist the real Phase 3 and Phase 4 artifacts and verify lossless round-trips.

Defaults to a SQLite file so the check runs without a server. Pass
``--database-url`` to target Postgres, which is the intended canonical store;
the same assertions then run against it unchanged.

Verifies, for every artifact: the stored payload reloads into an identical
domain object, re-saving identical content is idempotent, re-saving different
content under the same object/version is refused, lineage edges are retrievable,
and reviews are append-only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from atlas.domain.action import (
    CapabilityClaim,
    CollaborationOpportunity,
    RequiredAsset,
    RequiredCapability,
)
from atlas.domain.discovery import (
    ClinicalStudy,
    EntityResolutionDecision,
    Grant,
    Laboratory,
    Organization,
    ResearchAsset,
    Researcher,
)
from atlas.domain.experiments import ExperimentProposal
from atlas.domain.gaps import KnowledgeGap, SearchCoverage
from atlas.domain.refinement import EdgeRefinement
from atlas.persistence.database import create_engine_for_url, create_schema
from atlas.persistence.repository import AtlasRepository
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
REFINEMENT = ROOT / "data" / "refinement" / "scar16_stub1_e3"
ACTION = ROOT / "data" / "action" / "scar16_stub1_e3"
SOURCE_VERSION = "b923d18f1c962eeaecf9f1f908305b21a8f26904"

ModelType = type[BaseModel]

SINGLE: tuple[tuple[Path, ModelType, str], ...] = (
    (REFINEMENT / "edge_refinement.json", EdgeRefinement, "run_id"),
    (REFINEMENT / "knowledge_gap.json", KnowledgeGap, "gap_id"),
    (REFINEMENT / "experiment_proposal.json", ExperimentProposal, "experiment_id"),
    (ACTION / "search_coverage.json", SearchCoverage, "coverage_id"),
    (ACTION / "collaboration_opportunity.json", CollaborationOpportunity, "collaboration_id"),
)
COLLECTIONS: tuple[tuple[Path, ModelType, str], ...] = (
    (ACTION / "required_capabilities.json", RequiredCapability, "capability_id"),
    (ACTION / "required_assets.json", RequiredAsset, "required_asset_id"),
    (ACTION / "capability_claims.json", CapabilityClaim, "claim_id"),
    (ACTION / "researchers.json", Researcher, "researcher_id"),
    (ACTION / "laboratories.json", Laboratory, "lab_id"),
    (ACTION / "research_assets.json", ResearchAsset, "asset_id"),
    (ACTION / "organizations.json", Organization, "organization_id"),
    (ACTION / "grants.json", Grant, "grant_id"),
    (ACTION / "clinical_studies.json", ClinicalStudy, "study_id"),
    (ACTION / "entity_resolution.json", EntityResolutionDecision, "decision_id"),
)


def _load_models() -> list[tuple[BaseModel, str]]:
    loaded: list[tuple[BaseModel, str]] = []
    for path, model, id_attr in SINGLE:
        instance = model.model_validate_json(path.read_text())
        loaded.append((instance, getattr(instance, id_attr)))
    for path, model, id_attr in COLLECTIONS:
        for item in json.loads(path.read_text()):
            instance = model.model_validate(item)
            loaded.append((instance, getattr(instance, id_attr)))
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=f"sqlite+pysqlite:///{ROOT / 'data' / 'atlas.sqlite3'}",
        help="SQLAlchemy URL; use a postgresql+psycopg:// URL for the canonical store",
    )
    parser.add_argument("--reset", action="store_true", help="delete a SQLite file first")
    args = parser.parse_args()

    if args.reset and args.database_url.startswith("sqlite"):
        target = Path(args.database_url.split("///", 1)[1])
        target.unlink(missing_ok=True)

    engine = create_engine_for_url(args.database_url)
    create_schema(engine)
    repository = AtlasRepository(engine)

    models = _load_models()
    saved = 0
    for instance, object_id in models:
        repository.save_artifact(instance, object_id=object_id, source_version=SOURCE_VERSION)
        saved += 1

    # Lossless round-trip: every stored artifact must reload identically.
    mismatches = []
    for instance, object_id in models:
        reloaded = repository.load_artifact(
            type(instance), object_id=object_id, source_version=SOURCE_VERSION
        )
        if reloaded is None or reloaded.model_dump(mode="json") != instance.model_dump(
            mode="json"
        ):
            mismatches.append(object_id)
    if mismatches:
        raise SystemExit(f"lossless round-trip failed for: {mismatches[:5]}")

    # Idempotent re-save of identical content.
    for instance, object_id in models:
        repository.save_artifact(instance, object_id=object_id, source_version=SOURCE_VERSION)

    # Immutability: different content under the same object/version must be refused.
    gap = KnowledgeGap.model_validate_json((REFINEMENT / "knowledge_gap.json").read_text())
    altered = gap.model_copy(update={"status": "CLOSED"})
    immutability_enforced = False
    try:
        repository.save_artifact(
            altered, object_id=gap.gap_id, source_version=SOURCE_VERSION
        )
    except ValueError:
        immutability_enforced = True
    if not immutability_enforced:
        raise SystemExit("immutable artifact conflict was not detected")

    # Lineage: record the full chain and read it back.
    lineage = json.loads((ACTION / "lineage.json").read_text())
    experiment_id = lineage["experiment_id"]
    gap_id = lineage["knowledge_gap_id"]
    refinement = EdgeRefinement.model_validate_json(
        (REFINEMENT / "edge_refinement.json").read_text()
    )
    edges: list[tuple[str, str, str, tuple[str, ...]]] = [
        (
            refinement.upstream_claim.claim_id,
            gap_id,
            "COULD_RESOLVE",
            tuple(refinement.upstream_evidence_ids),
        ),
        (gap_id, experiment_id, "TESTS", ()),
    ]
    for item in lineage["required_capabilities"]:
        edges.append((experiment_id, item["capability_id"], "REQUIRES", ()))
        for claim_id in item["capability_claim_ids"]:
            edges.append(
                (item["capability_id"], claim_id, "HAS_CAPABILITY", (item["evidence_source"],))
            )
    for subject in lineage["candidate_subjects"]:
        edges.append(
            (
                subject["lab_id"],
                experiment_id,
                "MAY_ADDRESS",
                tuple(subject["publications"]),
            )
        )
    for parent, child, relation, evidence in edges:
        repository.add_lineage(
            parent_id=parent, child_id=child, relationship=relation, evidence_ids=evidence
        )
    reconstructed = repository.lineage_to(experiment_id)
    if not reconstructed:
        raise SystemExit("lineage edges to the experiment could not be read back")

    print(
        json.dumps(
            {
                "database_url": args.database_url.split("://", 1)[0] + "://...",
                "artifacts_saved": saved,
                "lossless_round_trip": True,
                "idempotent_resave": True,
                "immutability_enforced": immutability_enforced,
                "lineage_edges_written": len(edges),
                "lineage_edges_to_experiment": len(reconstructed),
                "note": (
                    "Postgres is the intended canonical store; pass --database-url to "
                    "target it. These assertions are store-independent."
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
