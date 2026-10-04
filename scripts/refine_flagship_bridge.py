#!/usr/bin/env python3
"""Attempt to refine the flagship MechanisticBridge with deeper evidence.

Targets only the evidence already supporting the pair. A refinement must come
from a statement the source paper claims as its own finding; everything else
leaves v1 canonical and records NO_ADDITIONAL_BRIDGE_SPECIFICITY_SUPPORTED.

Nothing here names a disease, gene or pathway.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from atlas.adapters.europepmc.annotations import (
    MECHANISTIC_TYPES,
    EuropePmcAnnotationClient,
)
from atlas.adapters.literature.client import SnapshotFetcher
from atlas.domain.cross_disease import BridgeTermProvenance, MechanisticBridge
from atlas.services.cross_disease_pipeline import _FACTOR, MECHANISM_VOCABULARY
from atlas.services.cross_disease_pipeline import (
    _FACTOR_STOPWORDS as STOPWORDS,
)

ROOT = Path(__file__).resolve().parents[1]


def commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            cwd=ROOT, check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def terms_in(text: str) -> list[str]:
    """Mechanism vocabulary and regulator tokens present in one statement."""
    lowered = text.casefold()
    found = [term for term in MECHANISM_VOCABULARY if term.casefold() in lowered]
    found += [
        token for token in sorted(set(_FACTOR.findall(text)))
        if token not in STOPWORDS
    ]
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--journey", type=Path,
                        default=ROOT / "data/flagship/flagship_journey.json")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "data/flagship/bridge_refinement.json")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    journey = json.loads(args.journey.read_text())
    v1 = journey["validated_mechanistic_bridge"]
    evidence_ids = list(v1["derived_from_evidence_ids"])

    client = EuropePmcAnnotationClient(
        SnapshotFetcher(ROOT / "data/flagship/snapshots", offline=args.offline)
    )

    retrieval_report = []
    provenance: list[BridgeTermProvenance] = []
    for evidence_id in evidence_ids:
        article = client.annotations(evidence_id)
        retrieval_report.append({
            "source_id": evidence_id,
            "retrieved": article.retrieved,
            "failure_reason": article.failure_reason,
            "annotations": len(article.findings),
            "sections_seen": list(article.sections_seen),
            # The honest flag: did mining cover anything past the front matter?
            "full_text_sections_present": article.full_text_sections_present,
            "mechanistic_primary_findings": sum(
                1 for item in article.findings if item.can_refine_bridge
            ),
        })
        for finding in article.findings:
            if not finding.can_refine_bridge:
                continue
            for term in terms_in(finding.sentence):
                provenance.append(
                    BridgeTermProvenance(
                        term=term, source_id=evidence_id,
                        span=finding.sentence, annotation_type=finding.annotation_type,
                        finding_role=finding.role.value, section=finding.section,
                        snapshot_sha256=finding.snapshot_sha256,
                    )
                )

    # Deduplicate, keeping first provenance per term.
    unique: dict[str, BridgeTermProvenance] = {}
    for item in provenance:
        unique.setdefault(item.term, item)

    existing = {term.casefold() for term in v1["terms"]}
    new_terms = [term for term in unique if term.casefold() not in existing]

    any_full_text = any(row["full_text_sections_present"] for row in retrieval_report)
    outcome: dict[str, object] = {
        "schema_version": "bridge-refinement-v1",
        "software_commit": commit(),
        "generated_at": datetime.now(UTC).isoformat(),
        "parent_bridge": v1,
        "full_text_retrieval": retrieval_report,
        "full_text_obtained": any_full_text,
        "mechanistic_annotation_types_considered": sorted(MECHANISTIC_TYPES),
    }

    if not new_terms:
        outcome["result"] = "NO_ADDITIONAL_BRIDGE_SPECIFICITY_SUPPORTED"
        outcome["canonical_bridge"] = v1
        outcome["note"] = (
            "No statement claimed as a primary finding by its own paper "
            "contributed a term the v1 bridge did not already carry. v1 remains "
            "canonical."
        )
        args.out.write_text(json.dumps(outcome, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"result": outcome["result"],
                          "full_text_obtained": any_full_text}, indent=2))
        return 0

    merged = tuple(v1["terms"]) + tuple(new_terms)
    v2 = MechanisticBridge(
        bridge_id=f"{v1['bridge_id']}:v2",
        version=2,
        supersedes_bridge_id=v1["bridge_id"],
        refinement_reason=(
            f"{len(new_terms)} additional term(s) supported by statements their "
            "own papers claim as primary findings, which the v1 derivation "
            "missed because it required a term to appear in more than one "
            "source. A single paper's demonstrated result is stronger evidence "
            "than a term repeated as background across two."
        ),
        terms=merged,
        derived_from_evidence_ids=tuple(evidence_ids),
        statement=(
            "Refined from the supporting evidence's own primary findings. "
            + " ".join(
                f"{item.source_id}: \"{item.span[:150]}\"" for item in unique.values()
            )
        ),
        derivation_method="europepmc-typed-annotations-primary-role-v1",
        term_provenance=tuple(unique.values()),
        distinct_from_retrieval_features=tuple(
            v1["distinct_from_retrieval_features"]
        ),
    )
    outcome["result"] = "BRIDGE_REFINED"
    outcome["new_terms"] = new_terms
    outcome["canonical_bridge"] = v2.model_dump(mode="json")
    args.out.write_text(json.dumps(outcome, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "result": "BRIDGE_REFINED",
        "full_text_obtained": any_full_text,
        "v1_terms": v1["terms"],
        "new_terms": new_terms,
        "primary_findings_used": len(unique),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
