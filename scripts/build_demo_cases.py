#!/usr/bin/env python3
"""Assemble the multi-case UI contract from completed pipeline runs.

Three cases with deliberately different outcomes. The third has no defensible
connection at all, and is included for that reason: a demo that only shows
successes cannot show that the system is selective, and "we found nothing" is
the honest result for most disease pairs.

Cases where no flagship exists carry goal3 and goal2 as null rather than being
omitted, so the shape is uniform and the UI can render the absence rather than
having to special-case a missing key.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DISCLAIMER = {
    "headline": (
        "Machine-generated research hypothesis based on available evidence; "
        "expert review required before scientific or financial action."
    ),
    "not_a_medical_recommendation": True,
    "not_an_established_mechanism": True,
    "review_state": "PROVISIONAL_MACHINE_SYNTHESIS",
    "expert_signoff": "AWAITING_EXPERT_SIGNOFF",
}

NEGATIVE = {
    "INSUFFICIENT_EVIDENCE", "SHARED_TISSUE_CONTEXT", "RETRIEVAL_ARTIFACT",
    "SHARED_CELLULAR_PROCESS_NON_EQUIVALENT", "SHARED_PHENOTYPE_ONLY", "CONTRADICTED",
}


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    label: str
    why_included: str
    candidates_dir: Path
    flagship_dir: Path | None


def commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            cwd=ROOT, check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def load_traces(directory: Path) -> dict[str, dict]:
    traces: dict[str, dict] = {}
    for path in (directory / "traces").glob("*.json"):
        trace = json.loads(path.read_text())
        traces[trace["disease_b"]] = trace
    return traces


def build_goal1(candidates: dict, traces: dict[str, dict], flagship: dict | None) -> dict:
    evaluated = candidates["evaluated"]
    return {
        "candidates_retrieved": candidates["candidates_retrieved"],
        "candidates_evaluated": candidates["candidates_evaluated"],
        "candidate_neighbors": [
            {
                "rank": row.get("rank"),
                "name": row["pair"].replace("_", " "),
                "retrieval_reason": (traces.get(row["pair"], {}).get("retrieval_reasons") or [{}])[0].get("feature"),
                "identity": row["identity"],
                "independent": row["independent_discovery"],
                "relationship": row["relationship"],
                "retrieval_validity": row["retrieval_validity"],
                "has_bridge": bool(traces.get(row["pair"], {}).get("mechanistic_bridge")),
            }
            for row in evaluated
        ],
        "excluded_as_same_entity": [
            row["pair"].replace("_", " ") for row in evaluated
            if not row["independent_discovery"]
            and row["identity"] not in {"DISTINCT_DISEASE"}
        ],
        "rejected_examples": [
            {
                "name": row["pair"].replace("_", " "),
                "outcome": row["relationship"],
                "why": (traces.get(row["pair"], {}).get("final_rationale") or "")[:240],
            }
            for row in evaluated if row["relationship"] in NEGATIVE
        ],
        "selected_neighbor": (
            {"id": flagship["flagship"]["disease_b_id"],
             "name": flagship["flagship"]["disease_b"].replace("_", " ")}
            if flagship else None
        ),
    }


def build_case(spec: CaseSpec) -> dict:
    candidates = json.loads((spec.candidates_dir / "goal1_candidates.json").read_text())
    traces = load_traces(spec.candidates_dir)
    journey = None
    goal2 = None
    if spec.flagship_dir is not None:
        journey_path = spec.flagship_dir / "flagship_journey.json"
        if journey_path.exists():
            journey = json.loads(journey_path.read_text())
        goal2_path = spec.flagship_dir / "goal2_map.json"
        if not goal2_path.exists():
            goal2_path = ROOT / "data/action/flagship_goal2_map.json"
        if goal2_path.exists():
            goal2 = json.loads(goal2_path.read_text())

    case: dict = {
        "case_id": spec.case_id,
        "label": spec.label,
        "why_included": spec.why_included,
        "outcome": "FULL_CHAIN" if journey else "NO_DEFENSIBLE_CONNECTION",
        "starting_disease": {
            "id": candidates["anchor_id"],
            "name": candidates["anchor"].replace("_", " "),
        },
        "goal1": build_goal1(candidates, traces, journey),
        "goal3": None,
        "goal2": None,
        "provenance": {
            "software_commit": commit(),
            "candidates_from": str(spec.candidates_dir.relative_to(ROOT)),
        },
        "disclaimer": DISCLAIMER,
    }

    if journey is None:
        # The honest null. Stated as a finding rather than an empty screen.
        # Say which kind of empty result this is. "Nothing found" has more than
        # one cause, and collapsing them would hide the identity layer's work.
        evaluated = candidates["evaluated"]
        identity_excluded = [
            row for row in evaluated
            if not row["independent_discovery"] and row["identity"] != "DISTINCT_DISEASE"
        ]
        if len(identity_excluded) >= max(1, len(evaluated) // 2):
            case["no_connection_reason"] = "ALL_CANDIDATES_ARE_THE_SAME_ENTITY"
            case["no_connection_statement"] = (
                f"{len(identity_excluded)} of {len(evaluated)} retrieved neighbours "
                f"of {case['starting_disease']['name']} are the same disease entity "
                "under a different name, so none is an independent cross-disease "
                "finding. The evidence here is not weak -- the identity check is "
                "what stops it being reported as a discovery."
            )
        else:
            case["no_connection_reason"] = "NO_SUPPORTING_EVIDENCE"
            case["no_connection_statement"] = (
                f"No candidate neighbour of {case['starting_disease']['name']} "
                "survived evidence refinement. Every retrieved candidate was "
                "supported only by shared phenotype, with no evidence establishing "
                "a molecular link. The system reports this rather than selecting "
                "the least-weak candidate."
            )
        return case

    bridge = journey["validated_mechanistic_bridge"]
    flagship = journey["flagship"]
    trace = traces.get(flagship["disease_b"], {})
    case["goal1"].update({
        "why_this_matters": (
            "The pair was retrieved on a broad annotation. Whether that annotation "
            "is why the pair is real is decided by evidence, separately."
        ),
        "selection": journey.get("selection_decision", {}),
        "retrieval_reason": {
            "types": flagship["retrieval_reason"],
            "feature": flagship.get("retrieval_primary_feature"),
        },
        "identity_result": {
            "relation": trace.get("identity_relation"),
            "scoped": trace.get("scoped_identities") or [],
        },
        "validated_relationship": {
            "class": flagship["final_relationship"],
            "retrieval_validity": flagship["retrieval_validity"],
            "rationale": trace.get("final_rationale", ""),
            "evidence_ids": flagship["evidence_ids"],
        },
    })
    case["goal3"] = {
        "mechanistic_bridge": {
            "id": bridge["bridge_id"], "version": journey.get("bridge_version"),
            "supersedes": journey.get("bridge_supersedes"),
            "terms": bridge["terms"],
            "display_label": journey.get("bridge_display_label"),
            "derived_from": bridge["derived_from_evidence_ids"],
            "evidence_depth": bridge.get("evidence_depth"),
            "full_text_review_completed": bridge.get("full_text_review_completed"),
        },
        "knowledge_gap": {
            "id": journey["knowledge_gap"]["gap_id"],
            "question": journey["knowledge_gap"]["question"],
            "why_it_matters": journey["knowledge_gap"]["why_it_matters"],
            "missing_evidence": list(journey["knowledge_gap"]["missing_evidence_type"]),
        },
        # Every field the journey screens read. A case that carries less than
        # this renders another case's data in its place, which is worse than
        # rendering nothing.
        "experiment": {
            "id": journey["experiment"]["experiment_id"],
            "hypothesis": journey["experiment"]["hypothesis"],
            "competing_hypothesis": journey["experiment"]["competing_hypothesis"],
            "model_system": journey["experiment"]["model_system"],
            "comparator": journey["experiment"]["comparator"],
            "primary_readout": journey["experiment"]["primary_readout"],
            "secondary_readouts": list(journey["experiment"]["secondary_readouts"]),
            "limitations": list(journey["experiment"]["known_limitations"]),
        },
        "supports_if": journey["experiment"]["expected_result_if_supported"],
        "refutes_if": journey["experiment"]["expected_result_if_refuted"],
        "evidence_limitations": [
            "Full text was not obtained for the supporting papers.",
            (
                "The bridge rests on typed literature annotations covering title "
                "and abstract, not the full articles."
            ),
            "No direct cross-disease functional experiment has been located.",
        ],
        "review_status": "AWAITING_EXPERT_SIGNOFF",
        "evidence_status": "PROVISIONALLY_SUPPORTED",
    }
    if goal2:
        case["goal2"] = {
            "required_capabilities": [
                {"id": c["requirement_id"], "capability": c["capability"],
                 "why": c["why_required"], "status": c["status"]}
                for c in goal2["capability_coverage"]
            ],
            "existing_work": [
                {"capability": c["capability"], "status": c["status"],
                 "candidates": c["candidate_teams"],
                 "verification_gap": c["missing_verification"]}
                for c in goal2["capability_coverage"] if c["candidate_teams"]
            ],
            "assets": goal2["research_assets"],
            "asset_status": goal2["asset_status"],
            "missing_capabilities": [
                {"capability": c["capability"], "status": c["status"],
                 "note": c["missing_verification"]}
                for c in goal2["capability_coverage"]
                if c["status"] in {"MISSING", "UNKNOWN"}
            ],
            "coordination_opportunities": goal2["potential_coordination_opportunities"],
            "coordination_note": (
                "No sufficiently supported evidence of overlapping or duplicative "
                "programs was found in the searched evidence."
            ),
            "execution_topology": goal2["collaboration_topology"],
            "collaborator_status": goal2["collaborator_status"],
            "first_contact": goal2["first_contact"],
        }
    return case


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "data/demo/cases.json")
    args = parser.parse_args()

    specs = [
        CaseSpec(
            case_id="scar16",
            label="A connection found for the wrong reason",
            why_included=(
                "The full chain. Retrieved on a broad annotation, that explanation "
                "rejected on evidence, a different and more specific bridge derived, "
                "and the chain carried through to a concrete next step."
            ),
            candidates_dir=ROOT / "data/cross_disease",
            flagship_dir=ROOT / "data/flagship",
        ),
        CaseSpec(
            case_id="lafora",
            label="The same cluster found from the other direction",
            why_included=(
                "Anchoring on the neighbour independently recovers the original "
                "disease family, which is a consistency check the system was not "
                "asked to pass. It also reaches a different execution topology, so "
                "it is not a mirror of the first case."
            ),
            candidates_dir=ROOT / "data/cross_disease_lafora",
            flagship_dir=ROOT / "data/flagship_lafora",
        ),
        CaseSpec(
            case_id="ankylosing",
            label="The same method outside neurology",
            why_included=(
                "An immune disease, to answer whether this only works for one "
                "disease area. Five of eight candidates were rejected because "
                "their co-mention searches returned tens of thousands of papers "
                "-- a measure of how much each disease is studied, not of a "
                "relationship. What survived is specific."
            ),
            candidates_dir=ROOT / "data/cross_disease_as",
            flagship_dir=ROOT / "data/flagship_as",
        ),
        CaseSpec(
            case_id="zellweger",
            label="Six strong candidates, all the same disease",
            why_included=(
                "Every retrieved neighbour is the same entity under another "
                "name, so none is an independent cross-disease finding. A "
                "different kind of empty result from a disease with no evidence: "
                "here the evidence is strong and the identity layer is what "
                "stops it being reported as a discovery."
            ),
            candidates_dir=ROOT / "data/cross_disease_zsd",
            flagship_dir=None,
        ),
        CaseSpec(
            case_id="scar20",
            label="A disease where the system finds nothing",
            why_included=(
                "Every retrieved candidate was phenotype-only with no supporting "
                "evidence, so no relationship was reported. Included because a demo "
                "of successes alone cannot show that the system is selective."
            ),
            candidates_dir=ROOT / "data/cross_disease_scar20",
            flagship_dir=None,
        ),
    ]

    cases = [build_case(spec) for spec in specs]
    payload = {
        "schema_version": "demo-cases-v1",
        "software_commit": commit(),
        "case_count": len(cases),
        "default_case": "scar16",
        "cases": cases,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "cases": [
            {"id": c["case_id"], "anchor": c["starting_disease"]["name"],
             "outcome": c["outcome"],
             "neighbours": len(c["goal1"]["candidate_neighbors"]),
             "rejected": len(c["goal1"]["rejected_examples"]),
             "topology": (c["goal2"] or {}).get("execution_topology")}
            for c in cases
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
