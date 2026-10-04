"""Tests for the rebuildable graph projection over the real artifacts."""

from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

from atlas.graph.projection import (
    ALLOWED_RELATIONSHIPS,
    ProjectedRelationship,
    project,
)

ROOT = Path(__file__).parents[2]
REFINEMENT = ROOT / "data" / "refinement" / "scar16_stub1_e3"
ACTION = ROOT / "data" / "action" / "scar16_stub1_e3"


def _load(path: Path):  # type: ignore[no-untyped-def]
    return json.loads(path.read_text())


def build():  # type: ignore[no-untyped-def]
    return project(
        refinement=_load(REFINEMENT / "edge_refinement.json"),
        knowledge_gap=_load(REFINEMENT / "knowledge_gap.json"),
        experiment=_load(REFINEMENT / "experiment_proposal.json"),
        required_capabilities=_load(ACTION / "required_capabilities.json"),
        capability_claims=_load(ACTION / "capability_claims.json"),
        laboratories=_load(ACTION / "laboratories.json"),
        researchers=_load(ACTION / "researchers.json"),
        research_assets=_load(ACTION / "research_assets.json"),
        organizations=_load(ACTION / "organizations.json"),
        grants=_load(ACTION / "grants.json"),
        clinical_studies=_load(ACTION / "clinical_studies.json"),
        entity_resolution=_load(ACTION / "entity_resolution.json"),
        collaboration=_load(ACTION / "collaboration_opportunity.json"),
    )


class ProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.projection = build()

    def test_projection_is_deterministic(self) -> None:
        self.assertEqual(self.projection.to_json(), build().to_json())

    def test_no_dangling_relationship(self) -> None:
        self.assertEqual(self.projection.dangling_relationships(), ())

    def test_relationship_vocabulary_is_closed(self) -> None:
        for item in self.projection.relationships:
            self.assertIn(item.relationship, ALLOWED_RELATIONSHIPS)

    def test_unsupported_relationship_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProjectedRelationship(start_id="a", end_id="b", relationship="CAUSES")

    def test_expected_entity_labels_are_projected(self) -> None:
        labels = Counter(label for node in self.projection.nodes for label in node.labels)
        for expected in (
            "Claim",
            "Evidence",
            "KnowledgeGap",
            "Experiment",
            "RequiredCapability",
            "CapabilityClaim",
            "Laboratory",
            "Researcher",
            "ResearchAsset",
            "Organization",
            "Grant",
            "ClinicalStudy",
            "CollaborationOpportunity",
        ):
            self.assertIn(expected, labels, expected)

    def test_chain_is_traversable_from_upstream_claim_to_opportunity(self) -> None:
        edges: dict[str, set[str]] = {}
        for item in self.projection.relationships:
            edges.setdefault(item.start_id, set()).add(item.end_id)
        collaboration = _load(ACTION / "collaboration_opportunity.json")
        experiment_id = collaboration["experiment_id"]
        gap_id = collaboration["knowledge_gap_id"]
        upstream = _load(REFINEMENT / "edge_refinement.json")["upstream_claim"]["claim_id"]
        self.assertIn(experiment_id, edges[collaboration["collaboration_id"]])
        self.assertIn(gap_id, edges[experiment_id])
        self.assertIn(upstream, edges[gap_id])

    def test_derived_claims_point_back_to_the_curated_claim(self) -> None:
        upstream = _load(REFINEMENT / "edge_refinement.json")["upstream_claim"]["claim_id"]
        generated = [
            item
            for item in self.projection.relationships
            if item.relationship == "GENERATED_FROM"
        ]
        self.assertTrue(generated)
        for item in generated:
            self.assertEqual(item.end_id, upstream)

    def test_evidence_roles_are_preserved_on_edges(self) -> None:
        roles = {
            item.properties.get("evidence_role")
            for item in self.projection.relationships
            if item.relationship == "STUDIES"
        }
        self.assertIn("direct_refuting", roles)
        self.assertIn("background_only", roles)

    def test_laboratories_only_may_address_an_experiment(self) -> None:
        labs = {item["lab_id"] for item in _load(ACTION / "laboratories.json")}
        for item in self.projection.relationships:
            if item.start_id in labs and item.end_id.startswith("experiment:"):
                self.assertEqual(item.relationship, "MAY_ADDRESS")

    def test_asset_reuse_is_projected_as_may_reuse_with_status(self) -> None:
        reuse = [
            item for item in self.projection.relationships if item.relationship == "MAY_REUSE"
        ]
        self.assertTrue(reuse)
        for item in reuse:
            self.assertEqual(item.properties["reuse_status"], "REQUIRES_VALIDATION")

    def test_possible_duplicate_is_projected_without_merging_nodes(self) -> None:
        same_as = [
            item
            for item in self.projection.relationships
            if item.relationship == "POSSIBLY_SAME_AS"
        ]
        self.assertTrue(same_as)
        for item in same_as:
            self.assertNotEqual(item.start_id, item.end_id)
            self.assertIn(item.properties["status"], {"POSSIBLE_DUPLICATE", "DISTINCT"})
            self.assertIn(item.start_id, self.projection.node_ids())
            self.assertIn(item.end_id, self.projection.node_ids())

    def test_capability_claim_status_survives_projection(self) -> None:
        claims = {
            item["claim_id"]: item["status"] for item in _load(ACTION / "capability_claims.json")
        }
        projected = {
            node.node_id: node.properties["status"]
            for node in self.projection.nodes
            if "CapabilityClaim" in node.labels
        }
        self.assertEqual(projected, claims)


if __name__ == "__main__":
    unittest.main()
