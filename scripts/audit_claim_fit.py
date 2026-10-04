#!/usr/bin/env python3
"""Run the claim-fit audit over every real DisMech entry.

Produces a machine-readable findings file plus per-detector counts and examples.
Every finding is a risk flag for curator review, never a proven error; each
detector's false-positive mode travels with its results so the list cannot be
read as a defect list.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import yaml
from atlas.services.claim_fit_audit import audit_document, detectors

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--disorders-dir",
        type=Path,
        default=ROOT / "data/upstream/dismech-checkout/kb/disorders",
    )
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "data/audit/claim_fit.json")
    parser.add_argument("--examples-per-detector", type=int, default=6)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    specs = detectors()
    paths = sorted(args.disorders_dir.glob("*.yaml"))
    if args.limit:
        paths = paths[: args.limit]

    all_findings = []
    per_disease: Counter[str] = Counter()
    failures = []
    for path in paths:
        try:
            document = yaml.safe_load(path.read_text())
        except Exception as exc:  # noqa: BLE001 - reported, never hidden
            failures.append({"file": path.name, "error": str(exc)[:200]})
            continue
        if not isinstance(document, dict):
            continue
        findings = audit_document(document, path.name)
        for finding in findings:
            spec = specs[finding.code]
            spec.count += 1
            if len(spec.examples) < args.examples_per_detector:
                spec.examples.append(finding)
            per_disease[path.name] += 1
        all_findings.extend(findings)

    payload = {
        "schema_version": "claim-fit-audit-v1",
        "dismech_commit": args.commit,
        "files_examined": len(paths),
        "files_failed": failures,
        "framing": (
            "Every entry below is a risk flag for curator review, not a proven error. "
            "Each detector states the question it asks and the way it can be wrong."
        ),
        "total_findings": len(all_findings),
        "detectors": [
            {
                "code": spec.code,
                "severity": spec.severity.value,
                "question": spec.question,
                "false_positive_mode": spec.false_positive_mode,
                "documented_as": spec.documented_as,
                "findings": spec.count,
                "examples": [
                    {
                        "disease_file": item.disease_file,
                        "object_path": item.object_path,
                        "object_name": item.object_name,
                        "detail": item.detail,
                        "references": list(item.references),
                        "curator_check": item.curator_check,
                    }
                    for item in spec.examples
                ],
            }
            for spec in sorted(specs.values(), key=lambda s: -s.count)
        ],
        "most_flagged_diseases": [
            {"file": name, "findings": count} for name, count in per_disease.most_common(15)
        ],
        "findings": [
            {
                "code": item.code,
                "severity": item.severity.value,
                "disease_file": item.disease_file,
                "object_path": item.object_path,
                "object_name": item.object_name,
                "detail": item.detail,
                "references": list(item.references),
            }
            for item in all_findings
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "files_examined": payload["files_examined"],
                "files_failed": len(failures),
                "total_findings": payload["total_findings"],
                "by_detector": {
                    spec.code: spec.count
                    for spec in sorted(specs.values(), key=lambda s: -s.count)
                },
                "diseases_with_any_finding": len(per_disease),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
