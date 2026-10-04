#!/usr/bin/env python3
"""Emit the rebuildable graph projection of the refinement and action chain.

Neo4j is a traversal index, not the source of truth. This script writes the
projection as JSON so it can be replayed into a graph database and dropped and
rebuilt at any time from the committed artifacts (or from Postgres).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from atlas.graph.projection import project

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refinement", type=Path, default=ROOT / "data/refinement/scar16_stub1_e3")
    parser.add_argument("--action", type=Path, default=ROOT / "data/action/scar16_stub1_e3")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    refinement_dir = args.refinement
    action_dir = args.action
    projection = project(
        refinement=_load(refinement_dir / "edge_refinement.json"),
        knowledge_gap=_load(refinement_dir / "knowledge_gap.json"),
        experiment=_load(refinement_dir / "experiment_proposal.json"),
        required_capabilities=_load(action_dir / "required_capabilities.json"),
        capability_claims=_load(action_dir / "capability_claims.json"),
        laboratories=_load(action_dir / "laboratories.json"),
        researchers=_load(action_dir / "researchers.json"),
        research_assets=_load(action_dir / "research_assets.json"),
        organizations=_load(action_dir / "organizations.json"),
        grants=_load(action_dir / "grants.json"),
        clinical_studies=_load(action_dir / "clinical_studies.json"),
        entity_resolution=_load(action_dir / "entity_resolution.json"),
        collaboration=_load(action_dir / "collaboration_opportunity.json"),
    )
    dangling = projection.dangling_relationships()
    if dangling:
        raise SystemExit(
            f"projection has {len(dangling)} dangling relationship(s); refusing to emit"
        )
    output = args.output or (action_dir / "graph_projection.json")
    output.write_text(projection.to_json() + "\n", encoding="utf-8")
    labels: dict[str, int] = {}
    for node in projection.nodes:
        for label in node.labels:
            labels[label] = labels.get(label, 0) + 1
    relationships: dict[str, int] = {}
    for item in projection.relationships:
        relationships[item.relationship] = relationships.get(item.relationship, 0) + 1
    print(
        json.dumps(
            {
                "output": str(output),
                "projection_version": projection.projection_version,
                "nodes": len(projection.nodes),
                "relationships": len(projection.relationships),
                "nodes_by_label": dict(sorted(labels.items())),
                "relationships_by_type": dict(sorted(relationships.items())),
                "dangling": len(dangling),
                "note": "Rebuildable index; Postgres remains the source of truth.",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
