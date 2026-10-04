#!/usr/bin/env python3
"""Generate mechanistic fingerprints for every imported disease.

Writes JSON Lines so the set streams rather than loading whole, and a summary
recording feature coverage, which determines what cross-disease comparison is
possible at all.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from atlas.adapters.dismech import DisMechImporter
from atlas.domain.fingerprint import FINGERPRINT_VERSION
from atlas.services.fingerprint_builder import build_fingerprint

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--disorders-dir",
        type=Path,
        default=ROOT / "data/upstream/dismech-checkout/kb/disorders",
    )
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "data/fingerprints/fingerprints.jsonl")
    parser.add_argument("--summary", type=Path, default=ROOT / "data/fingerprints/summary.json")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    importer = DisMechImporter(source_version=args.commit)
    paths = sorted(args.disorders_dir.glob("*.yaml"))
    if args.limit:
        paths = paths[: args.limit]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    class_counts: Counter[str] = Counter()
    feature_frequency: Counter[str] = Counter()
    missing_counts: Counter[str] = Counter()
    failures = []
    written = 0
    totals: Counter[str] = Counter()

    with args.output.open("w", encoding="utf-8") as handle:
        for path in paths:
            try:
                imported = importer.load_path(path)
                fingerprint = build_fingerprint(imported)
            except Exception as exc:  # noqa: BLE001 - reported, never hidden
                failures.append({"file": path.name, "error": re.sub(r"\s+", " ", str(exc))[:200]})
                continue
            handle.write(fingerprint.model_dump_json() + "\n")
            written += 1
            for name, count in fingerprint.coverage.features_by_class.items():
                class_counts[name] += count
            for feature in fingerprint.features:
                feature_frequency[feature.feature_id] += 1
            for dimension in fingerprint.coverage.missing_dimensions:
                missing_counts[dimension] += 1
            totals["features"] += len(fingerprint.features)
            totals["ontology_grounded"] += fingerprint.coverage.ontology_grounded_features
            totals["free_text"] += fingerprint.coverage.free_text_features
            totals["phenotypes"] += len(fingerprint.phenotype_ids)
            totals["genes"] += len(fingerprint.gene_ids)

    # A feature shared by almost every disease carries little information; one
    # shared by a handful is what makes a neighbour interesting.
    shared = [(fid, n) for fid, n in feature_frequency.items() if n > 1]
    summary = {
        "schema_version": "fingerprint-summary-v1",
        "fingerprint_version": FINGERPRINT_VERSION,
        "dismech_commit": args.commit,
        "diseases_examined": len(paths),
        "fingerprints_written": written,
        "failures": failures,
        "totals": dict(totals),
        "features_by_class": dict(class_counts.most_common()),
        "distinct_features": len(feature_frequency),
        "features_shared_by_more_than_one_disease": len(shared),
        "most_common_features": [
            {"feature_id": fid, "diseases": n} for fid, n in feature_frequency.most_common(20)
        ],
        "diseases_missing_dimension": dict(missing_counts.most_common()),
        "note": (
            "A fingerprint describes a disease; it asserts nothing about any other "
            "disease. Shared features make two diseases candidate neighbours only."
        ),
    }
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "fingerprints": written,
                "failures": len(failures),
                "distinct_features": summary["distinct_features"],
                "shared_features": summary["features_shared_by_more_than_one_disease"],
                "features_by_class": summary["features_by_class"],
                "mean_features_per_disease": round(totals["features"] / max(written, 1), 1),
                "output_mb": round(args.output.stat().st_size / 1e6, 1),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
