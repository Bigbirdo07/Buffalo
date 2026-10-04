#!/usr/bin/env python3
"""Goal 2: what exists, who has demonstrated it, what is missing.

Three distinct questions, kept distinct:
  A. who has a capability we need
  B. what assets already exist that could be reused
  C. is another group already pursuing overlapping work

Each required capability is searched independently, because no single group is
expected to hold a model of each disease and the assay. Nothing here names a
disease, gene or pathway: every query term is derived from the frozen experiment.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from atlas.adapters.literature.client import (
    PubMedClient,
    RetrievalError,
    SnapshotFetcher,
)
from atlas.domain.cross_disease import (
    CapabilityRecency,
    CollaborationTopology,
    CoverageStatus2,
    ModelAvailability,
    PotentialCoordinationOpportunity,
)

ROOT = Path(__file__).resolve().parents[1]
THIS_YEAR = 2026

# Vocabulary describing a research model or reagent. Methods vocabulary, no
# disease or gene, used to tell an asset-bearing paper from a methods paper.
ASSET_MARKERS = re.compile(
    r"\b(iPSC|induced pluripotent|cell line|knock-?in|knock-?out|knockout|"
    r"mouse model|murine|zebrafish|organoid|patient-derived|plasmid|construct|"
    r"antibod\w+|reporter|transgenic|isogenic|biobank|repository|registry)\b",
    re.IGNORECASE,
)


def commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            cwd=ROOT, check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def recency_of(year: int | None) -> CapabilityRecency:
    """Classify evidence age. Historical is not rejected, only flagged."""
    if year is None:
        return CapabilityRecency.UNKNOWN
    age = THIS_YEAR - year
    if age <= 3:
        return CapabilityRecency.CURRENT
    if age <= 8:
        return CapabilityRecency.RECENT
    return CapabilityRecency.HISTORICAL


def quoted(term: str) -> str:
    cleaned = term.strip()
    return f'"{cleaned}"[tiab]' if " " in cleaned or "-" in cleaned else f"{cleaned}[tiab]"


# A capability query returning more than this is not identifying a capability.
#
# Measured, not guessed. The first run ORed a bare protein acronym into a disease
# query and returned 84,485 hits whose top authors worked on an unrelated
# condition sharing the acronym, then marked the capability COVERED. Two other
# capabilities returned over 120,000 hits of unrelated biology. A result set that
# large means the search failed to be specific, and candidates drawn from it are
# noise wearing a name.
MAX_INFORMATIVE_HITS = 2000

# Acronyms are collision-prone, so they may never stand alone in a query. This is
# the same rule the evidence pipeline already applies, which this search failed
# to inherit.
_ACRONYM = re.compile(r"^[A-Z][A-Z0-9]{1,7}$")


def capability_queries(capability: dict, context: dict) -> list[str]:
    """Build independent, CONSTRAINED queries for one atomic capability.

    Conjunctive, not disjunctive. ORing a capability's terms together asks "has
    anyone ever written about any of these", which the corpus always answers yes
    to. ANDing them against a context term asks whether a group has demonstrated
    this capability in a relevant setting, which is the actual question.

    A bare acronym is never used alone, and a capability with nothing to
    constrain it yields no query rather than an unconstrained one: no search is
    more honest than a search that cannot discriminate.
    """
    terms = [item for item in capability["search_terms"] if item]
    if not terms:
        return []
    acronyms = [item for item in terms if _ACRONYM.match(item)]
    specific = [item for item in terms if not _ACRONYM.match(item)]

    anchors = capability.get("context_terms") or context.get("cell_terms") or []
    queries: list[str] = []

    if specific:
        core = "(" + " OR ".join(quoted(item) for item in specific) + ")"
        if anchors:
            queries.append(
                core + " AND (" + " OR ".join(quoted(a) for a in anchors) + ")"
            )
        elif len(specific) == 1 and " " in specific[0]:
            # A single multi-word term is specific enough to stand alone.
            queries.append(core)
    # An acronym only enters a query alongside a specific term that disambiguates
    # it, never on its own.
    if acronyms and specific:
        queries.append(
            "(" + " OR ".join(quoted(a) for a in acronyms) + ") AND ("
            + " OR ".join(quoted(item) for item in specific) + ")"
        )
    return queries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--journey", type=Path,
                        default=ROOT / "data/flagship/flagship_journey.json")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "data/action/flagship_goal2_map.json")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--retmax", type=int, default=12)
    args = parser.parse_args()

    journey = json.loads(args.journey.read_text())
    experiment = journey["experiment"]
    bridge = journey["validated_mechanistic_bridge"]
    flagship = journey["flagship"]

    # Atomic capabilities derived from the frozen experiment. Each is one thing
    # a group either can or cannot do, so each can be searched alone.
    node = bridge.get("terms", [])
    regulators = [item for item in node if item.isupper()]
    processes = [item for item in node if not item.isupper()]
    disease_a = flagship["disease_a"]
    disease_b = flagship["disease_b"].replace("_", " ")

    capabilities = [
        {
            "requirement_id": "cap:model-a",
            "capability": f"{disease_a} disease-relevant cellular model",
            "why_required": "The experiment needs one arm representing this disease.",
            # Disease name only. A bare gene or protein acronym here collided
            # with an unrelated condition sharing the abbreviation.
            "search_terms": [disease_a],
            "is_model": True,
        },
        {
            "requirement_id": "cap:model-b",
            "capability": f"{disease_b} disease-relevant cellular model",
            "why_required": "The experiment needs the comparison arm.",
            "search_terms": [disease_b],
            "is_model": True,
        },
        {
            "requirement_id": "cap:stress-challenge",
            "capability": "Standardised cellular stress challenge",
            "why_required": (
                "The bridge describes stress-responsive biology, so the "
                "comparison is made under challenge rather than at baseline."
            ),
            "search_terms": [*processes[-1:], "heat shock response"],
            "context_terms": ["proteostasis", "protein quality control", "neuron"],
            "is_model": False,
        },
        {
            "requirement_id": "cap:primary-assay",
            "capability": f"Functional assay reporting {bridge.get('terms', [''])[0]}",
            "why_required": "This is the primary readout; it decides the hypothesis.",
            "search_terms": [*regulators, *processes[:2]],
            "context_terms": [*processes[-1:], "proteostasis"],
            "is_model": False,
        },
        {
            "requirement_id": "cap:secondary-profiling",
            "capability": "Secondary molecular profiling",
            "why_required": (
                "Supporting context only. Cannot decide the hypothesis."
            ),
            "search_terms": ["diGly", "ubiquitinome", "ubiquitylome"],
            "is_model": False,
        },
    ]

    snapshots = args.out.parent / "goal2_snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    client = PubMedClient(SnapshotFetcher(snapshots, offline=args.offline))
    context = {"cell_terms": journey.get("cell_terms") or []}

    coverage: list[dict] = []
    assets: list[dict] = []
    all_teams: dict[str, list[dict]] = {}

    for capability in capabilities:
        queries = capability_queries(capability, context)
        hits: list[dict] = []
        searched: list[dict] = []
        for query in queries:
            try:
                total, pmids, digest = client.search(query, retmax=args.retmax)
                informative = total <= MAX_INFORMATIVE_HITS
                searched.append({
                    "query": query,
                    "status": "CHECKED" if informative else "TOO_BROAD_TO_IDENTIFY",
                    "total_hits": total, "snapshot": digest,
                    "note": None if informative else (
                        f"{total} hits exceeds {MAX_INFORMATIVE_HITS}: this query "
                        "cannot identify a capability, so no candidate is drawn "
                        "from it."
                    ),
                })
                if not informative:
                    continue
            except RetrievalError as error:
                searched.append({"query": query, "status": "FAILED",
                                 "error": str(error)[:160]})
                continue
            records = client.records(tuple(pmids)) if pmids else {}
            for pmid in pmids:
                record = records.get(pmid)
                if record is None or not record.authors:
                    continue
                name = (record.authors[-1].name or "").strip()
                if not name:
                    continue
                text = f"{record.title} {getattr(record, 'abstract', '') or ''}"
                hits.append({
                    "pmid": pmid, "title": record.title[:180], "year": record.year,
                    "last_author": name,
                    "recency": recency_of(record.year).value,
                    "mentions_asset": bool(ASSET_MARKERS.search(text)),
                })
        hits.sort(key=lambda row: -(row["year"] or 0))
        best = hits[:3]

        # Assets: a paper describing a model or reagent is evidence the thing
        # existed in that study, and nothing more.
        for hit in hits:
            if hit["mentions_asset"] and capability["is_model"]:
                assets.append({
                    "asset_id": f"asset:{capability['requirement_id']}:PMID-{hit['pmid']}",
                    "for_capability": capability["requirement_id"],
                    "description": hit["title"],
                    "source": f"PMID:{hit['pmid']}",
                    "year": hit["year"],
                    # Existence and availability are different facts.
                    "availability": ModelAvailability.MODEL_DEMONSTRATED.value
                    if hit["year"]
                    else ModelAvailability.MODEL_NOT_LOCATED.value,
                    "availability_note": (
                        "A publication shows this existed in that study. It does "
                        "not show the model is deposited, shareable, or still "
                        "maintained."
                    ),
                    "repository_checked": False,
                })

        if not queries:
            status = CoverageStatus2.UNKNOWN
            verify = (
                "No sufficiently specific query could be built from the "
                "experiment's terms, so this capability was not searched. "
                "Unknown, not absent."
            )
        elif all(row["status"] == "TOO_BROAD_TO_IDENTIFY" for row in searched):
            status = CoverageStatus2.UNKNOWN
            verify = (
                "Every query was too broad to identify a capability. This "
                "needs a narrower, expert-supplied search term."
            )
        elif not best:
            status = CoverageStatus2.MISSING
            verify = (
                "No candidate retrieved by the recorded searches. Absence here "
                "means these searches found none, not that none exists."
            )
        else:
            current = [h for h in best if h["recency"] in {"CURRENT", "RECENT"}]
            status = (
                CoverageStatus2.COVERED_SUPPORTED if current else CoverageStatus2.PARTIAL
            )
            verify = (
                "Confirm the group still performs this and would consider "
                "applying it to both disease contexts."
                if current
                else "Only historical evidence: HISTORICAL_CAPABILITY_REQUIRES_"
                     "CURRENT_VERIFICATION."
            )
        for hit in best:
            all_teams.setdefault(hit["last_author"], []).append(
                {"capability": capability["requirement_id"], "pmid": hit["pmid"],
                 "year": hit["year"]}
            )

        coverage.append({
            "requirement_id": capability["requirement_id"],
            "capability": capability["capability"],
            "why_required": capability["why_required"],
            "search_terms": capability["search_terms"],
            "source_types_searched": ["PubMed"],
            "searches": searched,
            "candidate_teams": [
                {
                    "name": hit["last_author"], "source": f"PMID:{hit['pmid']}",
                    "year": hit["year"], "recency": hit["recency"],
                    "evidence_scope": "TEAM_LEVEL",
                    "capability_verified": False,
                    "current_activity_supported": hit["recency"] == "CURRENT",
                    # Never inferred, under any evidence.
                    "collaboration_willingness": "UNKNOWN",
                }
                for hit in best
            ],
            "status": status.value,
            "missing_verification": verify,
        })

    # Coordination: a group demonstrating two or more required capabilities may
    # already be positioned to run part of this, which is worth knowing. This is
    # a question about overlap, never a claim that anyone is duplicating work.
    coordination: list[dict] = []
    multi = {
        name: rows for name, rows in all_teams.items()
        if len({row["capability"] for row in rows}) > 1
    }
    names = sorted(multi)
    for index, first in enumerate(names):
        for second in names[index + 1:]:
            shared = {r["capability"] for r in multi[first]} & {
                r["capability"] for r in multi[second]
            }
            if not shared:
                continue
            coordination.append(
                PotentialCoordinationOpportunity(
                    opportunity_id=f"coord:{index}:{second[:12]}",
                    group_a=first, group_b=second,
                    overlapping_objective=(
                        "Both groups have published work bearing on the same "
                        "required capabilities for this experiment."
                    ),
                    overlapping_capability=", ".join(sorted(shared)),
                    evidence_ids=tuple(
                        f"PMID:{r['pmid']}" for r in multi[first] + multi[second]
                    ),
                    uncertainty=(
                        "Overlap is inferred from publication topics alone. The "
                        "groups may already collaborate, may be replicating "
                        "deliberately, or may be approaching different questions."
                    ),
                    potential_benefit=(
                        "If unaware of each other, a shared protocol would make "
                        "the cross-disease comparison directly interpretable."
                    ),
                    verification_required=(
                        "Confirm each group's current focus before suggesting "
                        "any coordination."
                    ),
                ).model_dump(mode="json")
            )

    covered = [c for c in coverage if c["status"] in
               {"COVERED_VERIFIED", "COVERED_SUPPORTED"}]
    missing = [c for c in coverage if c["status"] == "MISSING"]
    critical_missing = [c for c in missing if "model" in c["requirement_id"]
                        or "primary-assay" in c["requirement_id"]]
    if critical_missing:
        topology = CollaborationTopology.PARTIALLY_EXECUTABLE
    elif not covered:
        topology = CollaborationTopology.NOT_CURRENTLY_EXECUTABLE
    elif len(covered) == len(coverage) and len(all_teams) == 1:
        topology = CollaborationTopology.SINGLE_GROUP_EXECUTABLE
    else:
        topology = CollaborationTopology.MULTI_PARTY_EXECUTABLE

    first_target = next(
        (
            team
            for row in coverage
            if row["requirement_id"] == "cap:primary-assay"
            for team in row["candidate_teams"]
            if team["current_activity_supported"]
        ),
        None,
    )

    payload = {
        "schema_version": "flagship-goal2-map-v1",
        "software_commit": commit(),
        "generated_at": datetime.now(UTC).isoformat(),
        "scientific_question": journey["knowledge_gap"]["question"],
        "frozen_bridge": {
            "bridge_id": bridge["bridge_id"], "version": bridge.get("version"),
            "terms": bridge["terms"],
            "evidence_depth": bridge.get("evidence_depth"),
            "full_text_review_completed": bridge.get("full_text_review_completed"),
        },
        "primary_readout": experiment["primary_readout"],
        "capability_coverage": coverage,
        "research_assets": assets or [],
        "asset_status": "NO_RELEVANT_ASSET_IDENTIFIED" if not assets else "ASSETS_FOUND",
        "potential_coordination_opportunities": coordination,
        "collaboration_topology": topology.value,
        "collaborator_status": "NO_VERIFIED_COLLABORATOR_IDENTIFIED",
        "capabilities_total": len(coverage),
        "capabilities_covered": len(covered),
        "capabilities_missing": len(missing),
        "first_contact": {
            "target": first_target["name"] if first_target else None,
            "basis": f"PMID:{first_target['source']}" if first_target else None,
            "question": (
                f"Your group has published work using the assay cited above. We "
                f"are investigating whether {disease_a} and {disease_b} converge "
                f"on a shared defect in {', '.join(bridge['terms'][:3])}. Could "
                "your established assay be applied in parallel to both disease "
                "contexts under matched conditions, with a shared control?"
            ),
            "caveat": (
                "Capability is demonstrated by publication only. Willingness and "
                "current availability are unknown and must not be assumed."
            ),
        } if first_target else {
            "target": None,
            "question": None,
            "caveat": "No candidate has current-activity evidence for the primary assay.",
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "capabilities": len(coverage), "covered": len(covered),
        "missing": len(missing), "assets": len(assets),
        "coordination": len(coordination), "topology": topology.value,
        "first_contact": payload["first_contact"]["target"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
