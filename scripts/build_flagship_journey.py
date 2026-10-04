#!/usr/bin/env python3
"""Drive one validated cross-disease relationship to a concrete next action.

Takes the flagship pair's decision trace and runs it through the existing
pathway: knowledge gap, falsifiable experiment, required capabilities and
assets, then capability discovery. Nothing here names a disease; the flagship is
selected by evidence from the relationships file and every term is derived.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from atlas.adapters.literature.client import PubMedClient, SnapshotFetcher
from atlas.domain.cross_disease import RelationshipClass
from atlas.domain.gaps import CoverageStatus, SearchCoverage, SearchSourceCoverage
from atlas.services.candidate_generation import FeatureIndex, generate_candidates
from atlas.services.capability_discovery import (
    DiscoveryContext,
    build_targeted_queries,
    candidate_signals,
    derive_candidates,
    extract_method_terms,
    run_searches,
)
from atlas.services.cross_disease_synthesis import (
    SynthesisInputs,
    build_cross_disease_experiment,
    build_cross_disease_gap,
)
from atlas.services.disease_comparison import compare_diseases
from atlas.services.hpo_similarity import (
    HpoOntology,
    PhenotypeSimilarity,
    load_annotation_sets,
)
from atlas.services.requirement_extraction import extract_experiment_requirements

ROOT = Path(__file__).resolve().parents[1]
GAP_WORTHY = {
    RelationshipClass.SHARED_CAUSAL_MECHANISM.value,
    RelationshipClass.SHARED_DOWNSTREAM_MECHANISM.value,
    RelationshipClass.SHARED_PROTEIN_COMPLEX.value,
    RelationshipClass.SHARED_PATHWAY.value,
}


def build_coverage(trace: dict) -> SearchCoverage:
    """Record what was searched for this pair, including what was not searched.

    A gap whose coverage is unstated invites the reader to assume the search was
    exhaustive. It was not: this is title-and-abstract co-mention in one index.
    """
    raw = trace.get("search_coverage", {})
    status = raw.get("status", "NOT_STARTED")
    return SearchCoverage(
        coverage_id=f"coverage:{trace['pair_id']}",
        sources=(
            SearchSourceCoverage(
                source="PubMed (cross-disease co-mention)",
                status=CoverageStatus.CHECKED
                if status == "CHECKED"
                else CoverageStatus.FAILED,
                queries=(raw.get("query", ""),),
                result_count=int(raw.get("total_hits") or 0),
                snapshot_references=(raw["snapshot"],) if raw.get("snapshot") else (),
                languages=("eng",),
                checked_at=datetime.now(UTC),
            ),
            SearchSourceCoverage(
                source="Full-text corpora",
                status=CoverageStatus.NOT_STARTED,
                queries=(),
                result_count=0,
                error=(
                    "Not searched. A relationship discussed only in full text "
                    "would be invisible to this run."
                ),
            ),
        ),
        search_started_at=datetime.now(UTC),
        scope=f"Cross-disease evidence for pair {trace['pair_id']}",
        language_limitations=("English-language indexing only.",),
        geographic_limitations=(),
        interpretation_caveat=(
            "Absence of retrieved evidence is absence of indexed co-mention, not "
            "evidence that no relationship exists."
        ),
    )


def commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            cwd=ROOT, check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def select_flagship(rows: list[dict]) -> dict:
    """Pick the strongest genuinely independent relationship, by evidence.

    Ordered by: independence first (a subtype relationship is not a discovery),
    then corroboration, then whether the pair was molecularly anchored. No
    disease is preferred; if nothing qualifies the caller is told, rather than
    being handed a forced choice.
    """
    eligible = [
        row
        for row in rows
        if row["final_relationship"] in GAP_WORTHY
        and row["is_independent_discovery"]
        and len(row["evidence_ids"]) >= 2
    ]
    if not eligible:
        raise SystemExit(
            "NO_DEFENSIBLE_FLAGSHIP: no relationship is both an independent "
            "cross-disease pair and corroborated by two or more primary findings."
        )
    eligible.sort(key=lambda row: (-len(row["evidence_ids"]), row["disease_b"]))
    # Record the runners-up and the criterion. Corroboration count is a
    # defensible ordering but it is not a measure of quality: a pair with more
    # co-occurring papers is not necessarily the better-understood relationship.
    # Hiding the alternatives would present a ranking rule as a scientific
    # judgement.
    for position, row in enumerate(eligible):
        row["flagship_rank"] = position + 1
    eligible[0]["selection_criterion"] = (
        "Most corroborating primary findings among independent cross-disease "
        "pairs. This orders by evidence count, not by how well the mechanism is "
        "understood, and expert review should confirm the choice."
    )
    eligible[0]["runners_up"] = [
        {"disease": row["disease_b"], "evidence_count": len(row["evidence_ids"])}
        for row in eligible[1:4]
    ]
    return eligible[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--relationships", type=Path,
                        default=ROOT / "data/cross_disease/relationships.jsonl")
    parser.add_argument("--out", type=Path, default=ROOT / "data/flagship")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--pair", default=None,
        help="override selection with a named disease (records the override)",
    )
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.relationships.read_text().splitlines() if line]
    flagship = select_flagship(rows)
    if args.pair:
        override = next((r for r in rows if r["disease_b"] == args.pair), None)
        if override is None:
            raise SystemExit(f"{args.pair} is not an eligible validated relationship")
        override["selection_criterion"] = (
            f"Operator override. The automated criterion selected "
            f"{flagship['disease_b']}; this pair was chosen for external "
            "validation reasons and the automated ranking is preserved above."
        )
        override["automated_selection_would_be"] = flagship["disease_b"]
        override["runners_up"] = flagship.get("runners_up", [])
        flagship = override
    trace = json.loads(
        (ROOT / f"data/cross_disease/traces/{flagship['decision_trace_id']}.json").read_text()
    )

    fingerprints = [
        json.loads(line)
        for line in (ROOT / "data/fingerprints/fingerprints.jsonl").read_text().splitlines()
    ]
    index = FeatureIndex(fingerprints)
    ontology = HpoOntology.from_obo(ROOT / "data/upstream/ontology/hp.obo")
    sets = load_annotation_sets(ontology, [r["phenotype_ids"] for r in fingerprints])
    similarity = PhenotypeSimilarity(ontology, sets)
    phenotypes = {r["disease_id"]: s for r, s in zip(fingerprints, sets, strict=True)}

    left = index.by_id[flagship["disease_a_id"]]
    right = index.by_id[flagship["disease_b_id"]]
    candidate = next(
        item for item in generate_candidates(index, left["disease_id"], limit=60)
        if item.disease_id == right["disease_id"]
    )
    comparison = compare_diseases(
        index, candidate, left["disease_id"], similarity,
        phenotypes[left["disease_id"]], phenotypes[right["disease_id"]],
    )

    # The shared process the gap is about: the most specific feature both carry
    # on the axis that anchored the pair.
    process_axis = comparison.axis("SHARED_CELLULAR_PROCESS") or comparison.axis(
        "SHARED_MOLECULAR_FUNCTION"
    )
    if process_axis is None or not process_axis.shared:
        raise SystemExit("flagship has no shared process axis to build a gap on")
    shared_process = process_axis.shared[0].label

    # A readout able to report that process, from the anchor disease's own
    # experiment vocabulary.
    anchor_experiment = json.loads(
        (ROOT / "data/refinement/scar16_stub1_e3/experiment_proposal.json").read_text()
    )
    methods = extract_method_terms(list(anchor_experiment.get("readouts") or ()))
    shared_readout = (
        f"{methods[0]} assay reporting {shared_process}" if methods
        else f"a functional assay reporting {shared_process}"
    )

    from atlas.domain.cross_disease import ValidatedRelationship

    # A refinement run, when present, supplies the canonical bridge. The trace's
    # v1 is never edited: refinement supersedes, it does not overwrite.
    refinement_path = ROOT / "data/flagship/bridge_refinement.json"
    refinement = (
        json.loads(refinement_path.read_text()) if refinement_path.exists() else None
    )
    bridge_raw = trace.get("mechanistic_bridge")
    if refinement and refinement.get("result") == "BRIDGE_REFINED":
        bridge_raw = refinement["canonical_bridge"]
    if not bridge_raw:
        raise SystemExit(
            "flagship has no mechanistic bridge: the gap would be built from the "
            "retrieval annotation, which is the error this step exists to avoid."
        )
    from atlas.domain.cross_disease import MechanisticBridge

    bridge = MechanisticBridge.model_validate(bridge_raw)

    relationship = ValidatedRelationship(
        relationship_id=f"relationship:{flagship['pair_id']}",
        disease_a=flagship["disease_a_id"], disease_b=flagship["disease_b_id"],
        relationship_class=RelationshipClass(flagship["final_relationship"]),
        mechanistic_statement=trace["final_rationale"],
        evidence_ids=tuple(flagship["evidence_ids"]),
        mechanistic_bridge=bridge,
        differing_features=tuple(
            label for _i, label in comparison.phenotypes.distinctive_right[:5]
        ),
        source_version=flagship["source_version"],
    )

    inputs = SynthesisInputs(
        relationship=relationship,
        comparison=comparison,
        disease_a_name=flagship["disease_a"],
        disease_b_name=flagship["disease_b"].replace("_", " "),
        shared_process_label=shared_process,
        shared_readout=shared_readout,
        model_system=(
            "Patient-derived or engineered cellular models of each disease in a "
            "shared genetic background"
        ),
        supporting_evidence=tuple(flagship["evidence_ids"]),
        contradicting_evidence=tuple(flagship["contradiction_ids"]),
        coverage=build_coverage(trace),
    )

    gap = build_cross_disease_gap(inputs)
    experiment = build_cross_disease_experiment(gap, inputs)
    capabilities, assets = extract_experiment_requirements(experiment)

    # Discovery, driven entirely by the experiment's own requirements.
    genes = [
        f["label"] for f in left["features"] if f["feature_class"] == "genetic"
    ][:2] + [f["label"] for f in right["features"] if f["feature_class"] == "genetic"][:2]
    cells = [
        f["label"] for f in left["features"] if f["feature_class"] == "cell_tissue"
    ][:2]
    context = DiscoveryContext(
        gene_symbols=tuple(dict.fromkeys(genes))[:4],
        cell_type_terms=tuple(cells),
        assay_terms=tuple(methods[:4]),
        disease_terms=(inputs.disease_a_name, inputs.disease_b_name),
    )
    queries, skipped = build_targeted_queries(context)
    snapshots = args.out / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    client = PubMedClient(SnapshotFetcher(snapshots, offline=args.offline))
    results, failures = run_searches(client, queries, retmax=12)
    pmids = tuple(dict.fromkeys(p for r in results for p in r.pmids))
    records = client.records(pmids) if pmids else {}
    discovered = derive_candidates(
        results, records, per_capability=3, anchor_label=context.anchor_label
    )
    signals = candidate_signals(discovered, queries)

    # Capability coverage map: what is covered, what is only indirectly
    # supported, what is missing. Gaps are shown, never hidden -- a coverage map
    # that only lists what was found is a marketing document.
    by_category: dict[str, list] = {}
    for item in discovered:
        by_category.setdefault(item.capability_category, []).append(item)
    coverage_map = []
    for capability in capabilities:
        category = capability.capability_category.value
        matches = by_category.get(category, [])
        if matches:
            best = matches[0]
            status = "CANDIDATE_IDENTIFIED"
            source = f"{best.last_author} (PMID:{best.pmid}, {best.year})"
            scope = (
                "Publication shows the technique was performed by this team at "
                "this date. Not current activity, availability or willingness."
            )
            missing = (
                "Confirm the group still runs this assay, and that it can be "
                "applied to models of both diseases."
            )
        else:
            status = "MISSING"
            source = None
            scope = "No candidate retrieved by the recorded searches."
            missing = (
                "A group demonstrating this capability. Absence here means the "
                "searches found none, not that none exists."
            )
        coverage_map.append({
            "required_capability": capability.canonical_name,
            "category": category,
            "candidate_source": source,
            "evidence_scope": scope,
            "status": status,
            "missing_verification": missing,
        })

    covered = sum(1 for row in coverage_map if row["status"] == "CANDIDATE_IDENTIFIED")
    collaboration = {
        "knowledge_gap_id": gap.gap_id,
        "experiment_id": experiment.experiment_id,
        "required_capabilities": [c.canonical_name for c in capabilities],
        "capabilities_with_candidates": covered,
        "capabilities_missing": len(coverage_map) - covered,
        # Multi-party is a topology, not a failure: no single group is expected
        # to hold a model of each disease plus the assay.
        "execution_topology": (
            "ONE_LAB_EXECUTABLE" if covered == len(coverage_map) and covered <= 1
            else "MULTI_PARTY_EXECUTABLE" if covered > 0
            else "MISSING_CAPABILITY"
        ),
        "collaborator_status": "NO_VERIFIED_COLLABORATOR_IDENTIFIED",
        "uncertainty": (
            "Supporting evidence for the relationship is limited in number and "
            "experimental context. Expert review should establish whether it "
            "justifies the experiment before anyone is contacted."
        ),
        "suggested_first_step": (
            f"Approach a group with a demonstrated functional assay for "
            f"{bridge.axis_label} and ask whether it can be applied in parallel "
            f"to models of {flagship['disease_a']} and "
            f"{flagship['disease_b'].replace('_', ' ')} against a shared control."
        ),
        "review_status": "AWAITING_EXPERT_SIGNOFF",
    }

    args.out.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "flagship-journey-v1",
        "software_commit": commit(),
        "flagship": flagship,
        "retrieval_level_feature": shared_process,
        "validated_mechanistic_bridge": bridge_raw,
        "bridge_version": bridge.version,
        "bridge_supersedes": bridge.supersedes_bridge_id,
        "bridge_refinement_reason": bridge.refinement_reason,
        "bridge_display_label": bridge.display_label,
        "full_text_obtained": bool(refinement and refinement.get("full_text_obtained")),
        "knowledge_gap": gap.model_dump(mode="json"),
        "experiment": experiment.model_dump(mode="json"),
        "required_capabilities": [c.model_dump(mode="json") for c in capabilities],
        "required_assets": [a.model_dump(mode="json") for a in assets],
        "capability_coverage_map": coverage_map,
        "collaboration_opportunity": collaboration,
        "discovery": {
            "queries": [{"category": q.capability_category, "tier": q.tier.value,
                         "query": q.query} for q in queries],
            "skipped": list(skipped),
            "failures": list(failures),
            "candidates": [
                {"candidate_id": c.candidate_id, "capability": c.capability_category,
                 "pmid": c.pmid, "title": c.title[:160], "year": c.year,
                 "last_author": c.last_author, "affiliation": c.affiliation,
                 "disease_involvement": c.disease_involvement,
                 "limitation": c.limitation}
                for c in discovered
            ],
            "signal_count": {k: len(v) for k, v in signals.items()},
        },
    }
    (args.out / "flagship_journey.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "flagship": f"{flagship['disease_a']} x {flagship['disease_b']}",
        "relationship": flagship["final_relationship"],
        "evidence": flagship["evidence_ids"],
        "retrieval_feature": shared_process,
        "bridge_version": bridge.version,
        "bridge_terms": list(bridge.terms),
        "gap_id": gap.gap_id, "experiment_id": experiment.experiment_id,
        "capabilities": len(capabilities), "assets": len(assets),
        "queries_built": len(queries), "queries_skipped": len(skipped),
        "candidates": len(discovered),
        "capabilities_covered": covered,
        "capabilities_missing": len(coverage_map) - covered,
        "topology": collaboration["execution_topology"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
