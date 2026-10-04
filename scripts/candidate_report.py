#!/usr/bin/env python3
"""Produce visible demo-candidate dimensions for local DisMech files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from atlas.adapters.dismech import DisMechImporter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("disorders_dir", type=Path)
    parser.add_argument("--source-version", required=True)
    args = parser.parse_args()
    importer = DisMechImporter(source_version=args.source_version)
    report: list[dict[str, object]] = []
    for path in sorted((*args.disorders_dir.glob("*.yaml"), *args.disorders_dir.glob("*.json"))):
        imported = importer.load_path(path)
        report.append(
            {
                "file": path.name,
                "disease": imported.disease.canonical_name,
                **imported.candidate_metrics.model_dump(),
            }
        )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

