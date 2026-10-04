#!/usr/bin/env python3
"""Build the searchable index over every imported disease.

The demo has deep analysis for five diseases. This index covers all of them, so
a visitor can type any disease in the corpus and get a real answer rather than a
dead end: its causal genes and the neighbours retrieval actually returns, with
the shared features that produced each match.

What it deliberately does not contain: any relationship claim. Candidate
retrieval says two diseases share annotated features; whether that means
anything is decided by evidence refinement, which has been run for five. The
`case_id` field marks those five, and everything downstream uses it to decide
between the full journey and a view that states its own limits.

Precomputed because retrieval is local and fast but not free, and because a
demo that depends on the venue's network is a demo that can fail.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from atlas.services.candidate_generation import FeatureIndex, generate_candidates

ROOT = Path(__file__).resolve().parents[1]

# Neighbours kept per disease. Six is enough to show the shape of a result
# without turning a 3,289-entry index into a file too large to ship.
NEIGHBOURS_PER_DISEASE = 6
FEATURES_PER_NEIGHBOUR = 3


def commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            cwd=ROOT, check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fingerprints", type=Path,
        default=ROOT / "data/fingerprints/fingerprints.jsonl",
    )
    parser.add_argument("--cases", type=Path, default=ROOT / "data/demo/cases.json")
    parser.add_argument("--out", type=Path, default=ROOT / "data/demo/browse_index.json")
    args = parser.parse_args()

    fingerprints = [
        json.loads(line)
        for line in args.fingerprints.read_text(encoding="utf-8").splitlines()
        if line
    ]
    index = FeatureIndex(fingerprints)

    # Map a disease name to the case that analysed it, so the UI can tell the
    # five apart from the rest without hardcoding any disease name.
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    case_by_name = {
        case["starting_disease"]["name"]: case["case_id"] for case in cases["cases"]
    }

    diseases = []
    for record in fingerprints:
        name = record["disease_name"].replace("_", " ").strip()
        genes = [
            item["label"]
            for item in record["features"]
            if item["feature_class"] == "genetic" and item["label"]
        ][:8]
        neighbours = [
            {
                "name": candidate.disease_name.replace("_", " ").strip(),
                "axes": len(candidate.methods),
                "information": candidate.total_information,
                "features": [
                    item.label
                    for item in candidate.top_features(FEATURES_PER_NEIGHBOUR)
                ],
            }
            for candidate in generate_candidates(
                index, record["disease_id"], limit=NEIGHBOURS_PER_DISEASE
            )
        ]
        diseases.append({
            "id": record["disease_id"],
            "name": name,
            "genes": genes,
            "phenotype_count": len(record.get("phenotype_ids") or ()),
            "neighbours": neighbours,
            # Null for all but the analysed five.
            "case_id": case_by_name.get(name) or case_by_name.get(record["disease_name"]),
        })

    diseases.sort(key=lambda item: item["name"])
    payload = {
        "schema_version": "browse-index-v1",
        "software_commit": commit(),
        "disease_count": len(diseases),
        "analysed_case_count": sum(1 for item in diseases if item["case_id"]),
        "neighbours_per_disease": NEIGHBOURS_PER_DISEASE,
        "limitation": (
            "Candidate neighbours are computed for every disease here. They record "
            "shared annotated features, not a validated relationship. Evidence "
            "refinement has been run only for the diseases carrying a case_id."
        ),
        "diseases": diseases,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")

    without = sum(1 for item in diseases if not item["neighbours"])
    print(json.dumps({
        "output": str(args.out.relative_to(ROOT)),
        "diseases": len(diseases),
        "with_a_case": payload["analysed_case_count"],
        "with_no_neighbours": without,
        "megabytes": round(args.out.stat().st_size / 1e6, 2),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
