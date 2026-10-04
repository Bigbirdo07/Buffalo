"""Rebuildable graph projection of the refinement and action chain.

Neo4j is a traversal index, never the source of truth, so this module is a pure
function: artifacts in, nodes and relationships out. Nothing here talks to a
database. A writer can replay the output into Neo4j, and because the projection
is deterministic it can always be dropped and rebuilt from Postgres.

The relationship vocabulary is fixed and deliberately avoids asserting causality
the evidence does not support: a laboratory `MAY_ADDRESS` an experiment, a gap
`COULD_RESOLVE` a claim. Only upstream DisMech causal edges use a causal
predicate, and they carry their own refinement status.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

ALLOWED_RELATIONSHIPS = frozenset(
    {
        "REQUIRES",
        "HAS_CAPABILITY",
        "HAS_ASSET",
        "STUDIES",
        "FUNDED_FOR",
        "AUTHORED",
        "OPERATES",
        "MAY_ADDRESS",
        "MAY_REUSE",
        "GENERATED_FROM",
        "TESTS",
        "COULD_RESOLVE",
        "POSSIBLY_SAME_AS",
    }
)


@dataclass(frozen=True, slots=True)
class ProjectedNode:
    node_id: str
    labels: tuple[str, ...]
    properties: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ProjectedRelationship:
    start_id: str
    end_id: str
    relationship: str
    properties: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.relationship not in ALLOWED_RELATIONSHIPS:
            raise ValueError(f"relationship {self.relationship!r} is not in the vocabulary")


@dataclass(frozen=True, slots=True)
class Projection:
    nodes: tuple[ProjectedNode, ...]
    relationships: tuple[ProjectedRelationship, ...]
    projection_version: str = "atlas-projection-v1"

    def node_ids(self) -> set[str]:
        return {node.node_id for node in self.nodes}

    def dangling_relationships(self) -> tuple[ProjectedRelationship, ...]:
        known = self.node_ids()
        return tuple(
            item
            for item in self.relationships
            if item.start_id not in known or item.end_id not in known
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "projection_version": self.projection_version,
                "nodes": [
                    {
                        "node_id": node.node_id,
                        "labels": list(node.labels),
                        "properties": dict(node.properties),
                    }
                    for node in self.nodes
                ],
                "relationships": [
                    {
                        "start_id": item.start_id,
                        "end_id": item.end_id,
                        "relationship": item.relationship,
                        "properties": dict(item.properties),
                    }
                    for item in self.relationships
                ],
            },
            indent=2,
            sort_keys=True,
        )


def _node(node_id: str, node_label: str, /, **properties: Any) -> ProjectedNode:
    """Build a node. The label is positional-only so a payload field named
    "label" (the experiment proposal has one) cannot collide with it."""
    return ProjectedNode(
        node_id=node_id,
        labels=(node_label,),
        properties={key: value for key, value in properties.items() if value is not None},
    )


def project(
    *,
    refinement: Mapping[str, Any],
    knowledge_gap: Mapping[str, Any],
    experiment: Mapping[str, Any],
    required_capabilities: Iterable[Mapping[str, Any]] = (),
    capability_claims: Iterable[Mapping[str, Any]] = (),
    laboratories: Iterable[Mapping[str, Any]] = (),
    researchers: Iterable[Mapping[str, Any]] = (),
    research_assets: Iterable[Mapping[str, Any]] = (),
    organizations: Iterable[Mapping[str, Any]] = (),
    grants: Iterable[Mapping[str, Any]] = (),
    clinical_studies: Iterable[Mapping[str, Any]] = (),
    entity_resolution: Iterable[Mapping[str, Any]] = (),
    collaboration: Mapping[str, Any] | None = None,
) -> Projection:
    """Project the chain deterministically. Ordering is stable for replay."""
    nodes: list[ProjectedNode] = []
    relationships: list[ProjectedRelationship] = []

    upstream = refinement["upstream_claim"]
    nodes.append(
        _node(
            upstream["claim_id"],
            "Claim",
            kind="CURATED",
            statement=upstream["normalized_statement"],
            source_version=upstream["provenance"]["source_version"],
            source_object_path=upstream["provenance"]["source_object_path"],
            refinement_status=upstream["refinement_status"],
        )
    )
    for item in refinement["atomic"]:
        claim = item["claim"]
        nodes.append(
            _node(
                claim["claim_id"],
                "Claim",
                kind="EXTRACTED",
                statement=claim["normalized_statement"],
                refinement_status=item["status"],
                rule_applied=item["rule_applied"],
            )
        )
        relationships.append(
            ProjectedRelationship(
                start_id=claim["claim_id"],
                end_id=upstream["claim_id"],
                relationship="GENERATED_FROM",
            )
        )
    for observation in refinement["observations"]:
        nodes.append(
            _node(
                observation["evidence_id"],
                "Evidence",
                source_identifier=observation["source_identifier"],
                origin=observation["origin"],
            )
        )
    for item in refinement["atomic"]:
        claim_id = item["claim"]["claim_id"]
        for role in (
            "direct_supporting",
            "direct_refuting",
            "direct_qualifying",
            "indirect",
            "background_only",
        ):
            for reference in item[role]:
                evidence_id = reference.split("#", 1)[0]
                relationships.append(
                    ProjectedRelationship(
                        start_id=claim_id,
                        end_id=evidence_id,
                        relationship="STUDIES",
                        properties={"evidence_role": role},
                    )
                )

    gap_id = knowledge_gap["gap_id"]
    nodes.append(
        _node(
            gap_id,
            "KnowledgeGap",
            question=knowledge_gap["question"],
            gap_type=knowledge_gap["gap_type"],
            status=knowledge_gap["status"],
        )
    )
    for claim_id in knowledge_gap["related_claims"]:
        relationships.append(
            ProjectedRelationship(
                start_id=gap_id, end_id=claim_id, relationship="COULD_RESOLVE"
            )
        )

    experiment_id = experiment["experiment_id"]
    nodes.append(
        _node(
            experiment_id,
            "Experiment",
            question=experiment["scientific_question"],
            label=experiment["label"],
            human_review_required=experiment["human_review_required"],
        )
    )
    relationships.append(
        ProjectedRelationship(start_id=experiment_id, end_id=gap_id, relationship="TESTS")
    )

    for capability in required_capabilities:
        nodes.append(
            _node(
                capability["capability_id"],
                "RequiredCapability",
                canonical_name=capability["canonical_name"],
                capability_category=capability["capability_category"],
                human_review_status=capability["human_review_status"],
            )
        )
        relationships.append(
            ProjectedRelationship(
                start_id=experiment_id,
                end_id=capability["capability_id"],
                relationship="REQUIRES",
            )
        )
    for claim in capability_claims:
        nodes.append(
            _node(
                claim["claim_id"],
                "CapabilityClaim",
                status=claim["status"],
                directness=claim["directness"],
                recency=claim["recency"],
                human_review_status=claim["human_review_status"],
            )
        )
        relationships.append(
            ProjectedRelationship(
                start_id=claim["claim_id"],
                end_id=claim["capability_id"],
                relationship="HAS_CAPABILITY",
                properties={"status": claim["status"]},
            )
        )
        relationships.append(
            ProjectedRelationship(
                start_id=claim["subject_id"],
                end_id=claim["claim_id"],
                relationship="HAS_CAPABILITY",
            )
        )
    for lab in laboratories:
        nodes.append(
            _node(
                lab["lab_id"],
                "Laboratory",
                canonical_name=lab["canonical_name"],
                institution=lab["institution"],
                official_url=lab.get("official_url"),
            )
        )
        relationships.append(
            ProjectedRelationship(
                start_id=lab["lab_id"], end_id=experiment_id, relationship="MAY_ADDRESS"
            )
        )
    for person in researchers:
        nodes.append(
            _node(
                person["researcher_id"],
                "Researcher",
                canonical_name=person["canonical_name"],
                institution=person.get("institution"),
                role=person.get("role"),
            )
        )
    for lab in laboratories:
        for researcher_id in lab.get("personnel", ()):
            relationships.append(
                ProjectedRelationship(
                    start_id=researcher_id,
                    end_id=lab["lab_id"],
                    relationship="AUTHORED",
                    properties={"basis": "co-authorship on the group's publications"},
                )
            )
    for asset in research_assets:
        nodes.append(
            _node(
                asset["asset_id"],
                "ResearchAsset",
                canonical_name=asset["canonical_name"],
                asset_type=asset["asset_type"],
                reuse_status=asset["reuse_status"],
                availability=asset["availability"],
            )
        )
        if asset.get("creator"):
            relationships.append(
                ProjectedRelationship(
                    start_id=asset["creator"],
                    end_id=asset["asset_id"],
                    relationship="HAS_ASSET",
                )
            )
        relationships.append(
            ProjectedRelationship(
                start_id=experiment_id,
                end_id=asset["asset_id"],
                relationship="MAY_REUSE",
                properties={"reuse_status": asset["reuse_status"]},
            )
        )
    for organization in organizations:
        nodes.append(
            _node(
                organization["organization_id"],
                "Organization",
                canonical_name=organization["canonical_name"],
                organization_type=organization["organization_type"],
            )
        )
        for asset_id in organization.get("assets", ()):
            relationships.append(
                ProjectedRelationship(
                    start_id=organization["organization_id"],
                    end_id=asset_id,
                    relationship="OPERATES",
                )
            )
    for grant in grants:
        nodes.append(
            _node(
                grant["grant_id"],
                "Grant",
                title=grant["title"],
                organization=grant["organization"],
                active=grant["active"],
                project_end=grant.get("project_end"),
            )
        )
    for study in clinical_studies:
        nodes.append(
            _node(
                study["study_id"],
                "ClinicalStudy",
                title=study["title"],
                overall_status=study["overall_status"],
            )
        )
    for decision in entity_resolution:
        relationships.append(
            ProjectedRelationship(
                start_id=decision["left_entity_id"],
                end_id=decision["right_entity_id"],
                relationship="POSSIBLY_SAME_AS",
                properties={
                    "status": decision["status"],
                    "human_review_status": decision["human_review_status"],
                },
            )
        )
    if collaboration is not None:
        nodes.append(
            _node(
                collaboration["collaboration_id"],
                "CollaborationOpportunity",
                status=collaboration["status"],
                missing_capability_count=len(collaboration["missing_capabilities"]),
            )
        )
        relationships.append(
            ProjectedRelationship(
                start_id=collaboration["collaboration_id"],
                end_id=experiment_id,
                relationship="MAY_ADDRESS",
            )
        )
        for participant in collaboration["participants"]:
            relationships.append(
                ProjectedRelationship(
                    start_id=participant["subject_id"],
                    end_id=collaboration["collaboration_id"],
                    relationship="MAY_ADDRESS",
                    properties={"proposed_role": participant["proposed_role"]},
                )
            )

    deduplicated_nodes = tuple(
        {node.node_id: node for node in nodes}.values()
    )
    deduplicated_relationships = tuple(
        {
            (item.start_id, item.end_id, item.relationship, json.dumps(
                dict(item.properties), sort_keys=True
            )): item
            for item in relationships
        }.values()
    )
    return Projection(
        nodes=tuple(sorted(deduplicated_nodes, key=lambda item: item.node_id)),
        relationships=tuple(
            sorted(
                deduplicated_relationships,
                key=lambda item: (item.start_id, item.relationship, item.end_id),
            )
        ),
    )
