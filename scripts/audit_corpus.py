#!/usr/bin/env python3
"""Import every real DisMech entry and report the field-level audit totals.

Writes a machine-readable summary (data/audit/corpus_audit.json) plus the
per-disease candidate metrics used for demo selection. Everything reported in
docs/REAL_IMPORT_AUDIT.md and docs/DEMO_DISEASE_CANDIDATES.md comes from here.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from atlas.adapters.dismech import DisMechImporter
from atlas.adapters.dismech.field_audit import FieldDisposition


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--disorders-dir", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metrics-output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    importer = DisMechImporter(source_version=args.commit)
    paths = sorted(args.disorders_dir.glob("*.yaml"))
    if args.limit:
        paths = paths[: args.limit]

    totals: Counter[str] = Counter()
    warning_counts: Counter[str] = Counter()
    disposition_paths: dict[str, set[str]] = {
        disposition.value: set() for disposition in FieldDisposition
    }
    preserved_sections: Counter[str] = Counter()
    failures: list[dict[str, str]] = []
    undeclared: Counter[str] = Counter()
    unretained: Counter[str] = Counter()
    metrics: list[dict[str, Any]] = []

    for path in paths:
        try:
            imported = importer.load_path(path)
        except Exception as exc:  # noqa: BLE001 - every failure is reported, not hidden
            failures.append(
                {
                    "file": path.name,
                    "error_type": type(exc).__name__,
                    "error": re.sub(r"\s+", " ", str(exc))[:300],
                }
            )
            continue
        totals["files_imported"] += 1
        totals["nodes"] += len(imported.graph.nodes)
        totals["edges"] += len(imported.graph.edges)
        totals["claims"] += len(imported.claims)
        totals["evidence"] += len(imported.evidence)
        totals["imported_gaps"] += len(imported.imported_gaps)
        totals["hypotheses"] += len(imported.hypotheses)
        totals["genes"] += len(imported.genes)
        totals["variants"] += len(imported.variants)
        totals["phenotypes"] += len(imported.phenotypes)
        totals["preserved_records"] += len(imported.preserved_records)
        for record in imported.preserved_records:
            preserved_sections[record.section] += 1
        for warning in imported.warnings:
            warning_counts[warning.code] += 1
        audit = imported.field_audit
        for observation in audit.observations:
            disposition_paths[observation.disposition.value].add(observation.path)
        for item in audit.undeclared_paths:
            undeclared[item] += 1
        for item in audit.unretained_top_level_paths:
            unretained[re.sub(r"\[\d+\]", "[]", item)] += 1
        metrics.append(
            {
                "file": path.name,
                "disease": imported.disease.canonical_name,
                "mondo_id": imported.disease.mondo_id,
                "category": imported.disease.disease_type,
                **imported.candidate_metrics.model_dump(),
            }
        )

    summary = {
        "dismech_commit": args.commit,
        "disorders_dir": str(args.disorders_dir),
        "files_seen": len(paths),
        "totals": {
            **{key: int(value) for key, value in sorted(totals.items())},
            "files_failed": len(failures),
            "undeclared_paths": len(undeclared),
            "unretained_top_level_items": int(sum(unretained.values())),
        },
        "distinct_field_paths_by_disposition": {
            key: len(value) for key, value in sorted(disposition_paths.items())
        },
        "normalized_field_paths": sorted(disposition_paths[FieldDisposition.NORMALIZED.value]),
        "preserved_field_paths": sorted(
            disposition_paths[FieldDisposition.PRESERVED_UNNORMALIZED.value]
        ),
        "preserved_records_by_section": dict(preserved_sections.most_common()),
        "warnings_by_code": dict(warning_counts.most_common()),
        "undeclared_paths": dict(undeclared.most_common()),
        "unretained_top_level_items": dict(unretained.most_common()),
        "import_failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_output.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "files_seen": summary["files_seen"],
                "totals": summary["totals"],
                "distinct_field_paths_by_disposition": summary[
                    "distinct_field_paths_by_disposition"
                ],
                "warnings_by_code": summary["warnings_by_code"],
                "import_failures": failures[:10],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
