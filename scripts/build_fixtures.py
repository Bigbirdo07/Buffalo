#!/usr/bin/env python3
"""Derive compact, immutable regression fixtures from real DisMech entries.

Trimming rule (deterministic, applied in this order):

1. Sections that the importer's graph construction depends on are kept whole:
   pathophysiology (including every ``downstream`` edge), phenotypes (including
   every ``sequelae`` edge), genetic, variants, mechanistic_hypotheses,
   discussions, has_subtypes, mappings, disease_term and the identity keys.
   Trimming these would break edge targets and fabricate dangling-target
   warnings that do not exist upstream.
2. Every ``evidence`` list anywhere in the document is capped at the first
   EVIDENCE_CAP entries, preserving order.
3. The bulk clinical/reference sections in BULK_SECTIONS are capped at the first
   BULK_CAP entries, preserving order.

Nothing is reordered, renamed or rewritten, so each retained value is upstream
verbatim. The manifest records the upstream filename, the pinned commit, the
SHA-256 of the untrimmed source bytes, the SHA-256 of the fixture, and the caps
used, so a reviewer can regenerate and compare.
"""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

EVIDENCE_CAP = 2
BULK_CAP = 2
BULK_SECTIONS = (
    "biochemical",
    "clinical_trials",
    "computational_models",
    "datasets",
    "definitions",
    "diagnosis",
    "differential_diagnoses",
    "environmental",
    "epidemiology",
    "external_assertions",
    "histopathology",
    "imaging_findings",
    "inheritance",
    "prevalence",
    "progression",
    "references",
    "stages",
    "transmission",
    "treatments",
)
KEEP_WHOLE = (
    "pathophysiology",
    "phenotypes",
    "genetic",
    "variants",
    "mechanistic_hypotheses",
    "discussions",
    "has_subtypes",
    "animal_models",
    "experimental_models",
)

FIXTURES = {
    "scar16": "Autosomal_Recessive_Spinocerebellar_Ataxia_16.yaml",
    "acan_short_stature": "ACAN-Related_Short_Stature_Spectrum.yaml",
    "wilson_disease": "Wilsons_Disease.yaml",
    "sanfilippo": "Sanfilippo_syndrome.yaml",
}


def cap_evidence(value: Any) -> Any:
    """Recursively cap every ``evidence`` list without touching anything else."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            if key == "evidence" and isinstance(child, list):
                result[key] = [cap_evidence(item) for item in child[:EVIDENCE_CAP]]
            else:
                result[key] = cap_evidence(child)
        return result
    if isinstance(value, list):
        return [cap_evidence(item) for item in value]
    return value


def trim(document: dict[str, Any]) -> dict[str, Any]:
    trimmed: dict[str, Any] = {}
    for key, value in document.items():
        if key in BULK_SECTIONS and isinstance(value, list):
            trimmed[key] = value[:BULK_CAP]
        else:
            trimmed[key] = value
    return cap_evidence(trimmed)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--disorders-dir", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, Any]] = []
    for name, filename in sorted(FIXTURES.items()):
        source = args.disorders_dir / filename
        raw = source.read_bytes()
        document = yaml.safe_load(raw)
        fixture = trim(document)
        body = yaml.safe_dump(fixture, sort_keys=False, allow_unicode=True, width=100)
        target = args.output_dir / f"{name}.yaml"
        target.write_text(body, encoding="utf-8")
        manifest.append(
            {
                "fixture": target.name,
                "upstream_file": f"kb/disorders/{filename}",
                "dismech_commit": args.commit,
                "upstream_sha256": sha256(raw).hexdigest(),
                "upstream_bytes": len(raw),
                "fixture_sha256": sha256(body.encode()).hexdigest(),
                "fixture_bytes": len(body.encode()),
                "pathophysiology_nodes": len(document.get("pathophysiology") or []),
                "phenotypes": len(document.get("phenotypes") or []),
            }
        )
    procedure = {
        "generator": "scripts/build_fixtures.py",
        "trim_rule": {
            "sections_kept_whole": list(KEEP_WHOLE),
            "evidence_list_cap": EVIDENCE_CAP,
            "bulk_section_cap": BULK_CAP,
            "bulk_sections": list(BULK_SECTIONS),
        },
        "notes": (
            "Values are upstream verbatim; only list lengths are reduced. Graph-bearing "
            "sections are untrimmed so imported node/edge structure matches upstream. "
            "Regenerate with the recorded commit and compare fixture_sha256 to verify."
        ),
        "fixtures": manifest,
    }
    (args.output_dir / "MANIFEST.json").write_text(
        json.dumps(procedure, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(procedure, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
