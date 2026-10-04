#!/usr/bin/env python3
"""Import one read-only DisMech disorder file into normalized JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from atlas.adapters.dismech import DisMechImporter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--source-version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    imported = DisMechImporter(source_version=args.source_version).load_path(args.source)
    args.output.write_text(imported.model_dump_json(indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "disease": imported.disease.canonical_name,
                "nodes": len(imported.graph.nodes),
                "edges": len(imported.graph.edges),
                "claims": len(imported.claims),
                "evidence": len(imported.evidence),
                "source_sha256": imported.snapshot.sha256,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

