#!/usr/bin/env python3
"""Run candidate disease pairs blind through the cross-disease decision pipeline.

Blindness is structural, not a promise. This script never opens
data/validation/cross_disease_round1.json, and the pipeline module cannot reach
a filesystem at all: it classifies the inputs it is handed. Evidence is retrieved
here, from PubMed, by searching for co-mention of the two diseases' own entity
terms -- so the evidence a pair gets depends on the pair, never on what a
reviewer concluded about it.

A separate script compares the output with the sealed verdicts afterwards.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from atlas.adapters.literature.client import PubMedClient, SnapshotFetcher
from atlas.adapters.uniprot.client import UniProtClient
from atlas.domain.cross_disease import (
    IDENTITY_CLASSES,
    NEGATIVE_CLASSES,
    RejectedCrossDiseaseCandidate,
    RelationshipClass,
    ReviewStatus,
)
from atlas.services.candidate_generation import FeatureIndex, generate_candidates
from atlas.services.cross_disease_pipeline import (
    MechanisticEvidence,
    default_retrieval_reasons,
    run_pipeline,
)
from atlas.services.disease_comparison import compare_diseases
from atlas.services.disease_identity import assess_identity
from atlas.services.hpo_similarity import (
    HpoOntology,
    PhenotypeSimilarity,
    load_annotation_sets,
)

ROOT = Path(__file__).resolve().parents[1]
SEALED = "data/validation/cross_disease_round1.json"

# A co-mention search returning more than this cannot establish a specific link.
#
# Measured, not assumed. A genuine, specific pair returns a handful of papers:
# the flagship pair returns 3. Running the pipeline on a well-studied immune
# disease returned 46,000-50,000 co-mentions for every candidate and marked all
# eight a shared downstream mechanism, with bridges made of "phosphorylation",
# "TNF" and "STAT3" -- terms the flagship selector already penalises as generic.
#
# At that scale the query measures how much each disease is written about, not
# whether they are related. The Goal 2 capability search already applies this
# rule; the evidence pipeline did not inherit it, and a disease area with a large
# literature is what exposed the gap.
MAX_INFORMATIVE_COMENTION = 2000

# Publication types that are not primary experimental findings. A review stating
# a link reports someone else's result, which the evidence rules treat as
# background rather than as a demonstration.
SECONDARY_MARKERS = re.compile(
    r"\b(review|overview|perspective|commentary|editorial|meta-analysis)\b",
    re.IGNORECASE,
)
# Wording that indicates a direct molecular relationship was examined, as
# opposed to two diseases merely appearing in one paper. Generic method
# vocabulary, naming no disease or gene.
DIRECT_LINK_MARKERS = re.compile(
    r"\b(interact\w*|bind\w*|complex|co-?immunoprecipitat\w*|substrate|"
    r"ubiquitinat\w*|phosphorylat\w*|stabilis\w*|stabiliz\w*|degrad\w*|"
    r"regulat\w*|colocaliz\w*|co-?localis\w*|epistat\w*|modifier)\b",
    re.IGNORECASE,
)


def install_blindness_guard() -> None:
    """Make blindness enforced rather than promised.

    An audit hook aborts the run if anything opens the sealed verdict file. A
    comment saying "we do not read this" is worth nothing; a process that dies
    if it tries is worth something. The hook covers the whole interpreter, so it
    also catches an accidental read from inside an imported module.
    """
    sealed = str((ROOT / SEALED).resolve())

    def hook(event: str, payload: tuple) -> None:
        if event == "open" and payload and str(payload[0]) == sealed:
            raise RuntimeError(
                "blind run attempted to open the sealed review verdicts: " + sealed
            )

    sys.addaudithook(hook)


def commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT, check=True
        ).stdout.strip()
    except Exception:  # noqa: BLE001 - provenance is best effort, never fatal
        return "unknown"


def entity_terms(record: dict, uniprot: UniProtClient | None = None) -> list[str]:
    """Searchable terms for one disease: causal genes, protein aliases, name.

    Protein aliases matter more than they look. A co-mention search built from
    HGNC symbols alone returned zero hits for a pair the literature does
    discuss, because papers name the proteins, not the genes. Without aliases a
    zero-hit search is indistinguishable from "no relationship exists", which is
    the most dangerous possible failure for this system.

    Disease names are normalised because upstream file-derived labels keep
    underscores, and an underscored token matches nothing in PubMed.
    """
    terms: list[str] = []
    genes = [
        feature["label"]
        for feature in record["features"]
        if feature["feature_class"] == "genetic" and feature["label"]
    ]
    for gene in genes[:3]:
        terms.append(gene)
        if uniprot is not None:
            terms.extend(uniprot.protein_names(gene).search_aliases[:3])
    terms.append(record["disease_name"].replace("_", " ").strip())
    return list(dict.fromkeys(terms))[:10]


def build_query(left: dict, right: dict, uniprot: UniProtClient | None = None) -> str:
    """Co-mention query: does any publication discuss both diseases' entities?"""

    def group(record: dict) -> str:
        parts = [
            f'"{term}"[tiab]' if " " in term else f"{term}[tiab]"
            for term in entity_terms(record, uniprot)
        ]
        return "(" + " OR ".join(parts) + ")"

    return f"{group(left)} AND {group(right)}"


def confirming_terms(record: dict, uniprot: UniProtClient | None = None) -> list[str]:
    """Terms unambiguous enough to CONFIRM a publication is about this disease.

    Deliberately narrower than the terms used to retrieve it. Broad aliases earn
    their place in a query by finding papers; they must not be trusted to
    identify one. A bare protein acronym is the clearest case: adding one to the
    query raised recall and destroyed precision, because a three-to-five letter
    acronym routinely collides with an unrelated assay or term, and the matched
    papers then entered the evidence set as if they established a mechanism.

    So confirmation uses gene symbols and multi-word protein names only. This is
    the same retrieval-versus-evidence separation the rest of the system runs on,
    applied one level down.
    """
    terms: list[str] = []
    genes = [
        feature["label"]
        for feature in record["features"]
        if feature["feature_class"] == "genetic" and feature["label"]
    ]
    for gene in genes[:3]:
        terms.append(gene)
        if uniprot is not None:
            names = uniprot.protein_names(gene)
            acronyms = {item.upper() for item in names.common_acronyms}
            for alias in names.search_aliases:
                # Multi-word names are specific; bare acronyms are not.
                if " " in alias and alias.upper() not in acronyms:
                    terms.append(alias)
    name = record["disease_name"].replace("_", " ").strip()
    if len(name.split()) > 1:
        terms.append(name)
    return list(dict.fromkeys(terms))


def acronyms_for(record: dict, uniprot: UniProtClient | None = None) -> list[str]:
    """Collision-prone short protein names for this disease's genes."""
    if uniprot is None:
        return []
    found: list[str] = []
    for feature in record["features"]:
        if feature["feature_class"] == "genetic" and feature["label"]:
            found.extend(uniprot.protein_names(feature["label"]).common_acronyms)
    return list(dict.fromkeys(found))


def assess_record(
    record, left: dict, right: dict, uniprot: UniProtClient | None = None
) -> MechanisticEvidence:
    """Classify one retrieved publication conservatively.

    Two judgements, both deliberately strict:

    * ``establishes_direct_link`` requires wording describing an actual molecular
      relationship. Two diseases named in one abstract is co-mention, which is a
      reason to read the paper, not evidence of shared mechanism.
    * ``is_primary_finding`` is false for anything that looks like a review,
      because a review restating a link reports someone else's result.
    """
    text = f"{record.title} {getattr(record, 'abstract', '') or ''}"
    lowered = text.lower()

    def present(terms: list[str]) -> bool:
        return any(term.lower() in lowered for term in terms)

    left_strict = confirming_terms(left, uniprot)
    right_strict = confirming_terms(right, uniprot)
    left_acronyms = acronyms_for(left, uniprot)
    right_acronyms = acronyms_for(right, uniprot)

    def acronym_present(acronyms: list[str]) -> bool:
        """Case-SENSITIVE acronym match.

        A protein acronym and a laboratory method frequently differ only in
        case -- the protein CHIP versus the assay ChIP -- and a method acronym
        co-occurs with essentially every gene, so a case-insensitive match
        confirmed unrelated method papers as mechanistic evidence for six of
        eight candidate pairs. PubMed cannot search case-sensitively, so the
        query stays broad and confirmation carries the discrimination.
        """
        return any(token in text for token in acronyms)

    left_sure, right_sure = present(left_strict), present(right_strict)
    # An ambiguous acronym may identify one side only when the other side is
    # confirmed unambiguously. A paper established to be about disease B that
    # also says "CHIP" is almost certainly using the protein sense; the same
    # acronym in a paper with no confirmed link to either disease is noise.
    # This is disambiguation by context, and it is the only route by which an
    # acronym is ever allowed to count as evidence.
    left_by_context = (not left_sure) and right_sure and acronym_present(left_acronyms)
    right_by_context = (not right_sure) and left_sure and acronym_present(right_acronyms)
    both = (left_sure or left_by_context) and (right_sure or right_by_context)
    disambiguated = left_by_context or right_by_context
    direct = bool(both and DIRECT_LINK_MARKERS.search(text))
    primary = not bool(SECONDARY_MARKERS.search(record.title))
    caveats: list[str] = []
    if disambiguated:
        caveats.append(
            "One disease is identified only by an ambiguous protein acronym, "
            "accepted because the other disease is named unambiguously in the "
            "same publication. Context disambiguation, not a direct match."
        )
    if not both:
        caveats.append(
            "Retrieved by a broad alias but no unambiguous identifier for both "
            "diseases appears in the text, so this publication does not confirm "
            "it is about this pair."
        )
    if both and not direct:
        caveats.append(
            "Both entities appear in this publication, but no wording describes a "
            "molecular relationship between them. Co-mention is not evidence."
        )
    if not primary:
        caveats.append("Appears to be a review; restates findings rather than showing them.")
    return MechanisticEvidence(
        evidence_id=f"PMID:{record.pmid}",
        polarity="SUPPORTS" if direct else "QUALIFIES",
        establishes_direct_link=direct,
        is_primary_finding=primary,
        statement=record.title[:300],
        text=text[:4000],
        caveats=tuple(caveats),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--anchor", required=True, help="query disease name")
    parser.add_argument("--pairs", nargs="*", default=[], help="candidate disease names")
    parser.add_argument(
        "--top", type=int, default=0,
        help="instead of named pairs, take the top N retrieved candidates",
    )
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--retmax", type=int, default=20)
    parser.add_argument("--out", type=Path, default=ROOT / "data/cross_disease")
    args = parser.parse_args()
    install_blindness_guard()

    fingerprints = [
        json.loads(line)
        for line in (ROOT / "data/fingerprints/fingerprints.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    index = FeatureIndex(fingerprints)
    ontology = HpoOntology.from_obo(ROOT / "data/upstream/ontology/hp.obo")
    sets = load_annotation_sets(ontology, [r["phenotype_ids"] for r in fingerprints])
    similarity = PhenotypeSimilarity(ontology, sets)
    phenotypes = {r["disease_id"]: s for r, s in zip(fingerprints, sets, strict=True)}
    by_name = {r["disease_name"]: r for r in fingerprints}

    anchor = by_name[args.anchor]
    retrieved = generate_candidates(index, anchor["disease_id"], limit=60)
    candidates = {item.disease_name: item for item in retrieved}
    # Goal 1 starts from a disease, not from a chosen pair: the neighbours must
    # emerge from retrieval rather than being supplied.
    pair_names = args.pairs or [item.disease_name for item in retrieved[: args.top]]
    if not pair_names:
        raise SystemExit("supply --pairs or --top")
    ranks = {item.disease_name: position + 1 for position, item in enumerate(retrieved)}

    snapshots = args.out / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    client = PubMedClient(SnapshotFetcher(snapshots, offline=args.offline))
    uniprot = UniProtClient(SnapshotFetcher(snapshots, offline=args.offline))

    args.out.mkdir(parents=True, exist_ok=True)
    traces_dir = args.out / "traces"
    traces_dir.mkdir(exist_ok=True)
    software_commit = commit()
    relationships: list[dict] = []
    rejected: list[dict] = []
    summary: list[dict] = []

    for name in pair_names:
        candidate = candidates.get(name)
        if candidate is None:
            summary.append({"pair": name, "status": "NOT_RETRIEVED"})
            continue
        other = by_name[name]
        pair_id = f"{anchor['disease_id'][:8]}-{other['disease_id'][:8]}"

        identity = assess_identity(
            anchor, other, similarity,
            phenotypes[anchor["disease_id"]], phenotypes[other["disease_id"]],
        )
        comparison = compare_diseases(
            index, candidate, anchor["disease_id"], similarity,
            phenotypes[anchor["disease_id"]], phenotypes[other["disease_id"]],
        )

        query = build_query(anchor, other, uniprot)
        evidence: list[MechanisticEvidence] = []
        coverage: dict[str, object] = {"query": query}
        try:
            total, pmids, digest = client.search(query, retmax=args.retmax)
            informative = total <= MAX_INFORMATIVE_COMENTION
            coverage.update({
                "status": "CHECKED" if informative else "TOO_BROAD_TO_ESTABLISH_LINK",
                "total_hits": total,
                "snapshot": digest,
                "note": None if informative else (
                    f"{total} co-mentioning papers exceeds {MAX_INFORMATIVE_COMENTION}. "
                    "At this scale the query reflects how much each disease is "
                    "studied, not a specific relationship between them, so no "
                    "evidence is drawn from it."
                ),
            })
            if informative:
                records = client.records(tuple(pmids))
                for pmid in pmids:
                    record = records.get(pmid)
                    if record is not None:
                        evidence.append(assess_record(record, anchor, other, uniprot))
        except Exception as error:  # noqa: BLE001 - a failed search is data
            coverage.update({"status": "FAILED", "error": str(error)[:200]})

        reasons = default_retrieval_reasons(
            candidate, anchor["disease_id"], other["disease_id"], "feature-index-v1"
        )
        trace, relationship = run_pipeline(
            pair_id=pair_id,
            candidate=candidate,
            comparison=comparison,
            identity_relation=identity.relation,
            identity_rationale=identity.rationale,
            identity_same_entity_scope=identity.has_same_entity_scope,
            scoped_identity_notes=tuple(
                f"{item.scope_label} -> {item.relation.value}" for item in identity.scoped
            ),
            evidence=tuple(evidence),
            retrieval_reasons=reasons,
            source_version=anchor["source_version"],
            ontology_versions={"hpo": "hp/releases/2026-09-01"},
        )

        trace_payload = {
            "pair_id": pair_id,
            "disease_a": anchor["disease_name"],
            "disease_b": other["disease_name"],
            "stages": [
                {"stage": s.stage, "finding": s.finding, "assessable": s.assessable}
                for s in trace.stages
            ],
            "identity_relation": identity.relation.value,
            "scoped_identities": [
                {
                    "scope": item.scope_label,
                    "relation": item.relation.value,
                    "rationale": item.rationale,
                }
                for item in identity.scoped
            ],
            "retrieval_reasons": [
                {
                    "type": r.reason_type.value,
                    "feature": r.source_feature,
                    "corpus_frequency": r.corpus_frequency,
                }
                for r in reasons
            ],
            "retrieval_validity": trace.retrieval_validity.value,
            "variant_compatibility": trace.variant_compatibility.value,
            "molecular_anchor_present": trace.molecular_anchor_present,
            "molecular_anchor_description": trace.molecular_anchor_description,
            "supporting_evidence_ids": list(trace.supporting_evidence_ids),
            "contradicting_evidence_ids": list(trace.contradicting_evidence_ids),
            "qualifying_evidence_ids": list(trace.qualifying_evidence_ids),
            "alternative_explanations": [
                {"code": a.code, "applies": a.applies, "description": a.description}
                for a in trace.alternative_explanations
            ],
            "mechanistic_bridge": (
                {
                    "bridge_id": trace.mechanistic_bridge.bridge_id,
                    "terms": list(trace.mechanistic_bridge.terms),
                    "statement": trace.mechanistic_bridge.statement,
                    "derived_from_evidence_ids": list(
                        trace.mechanistic_bridge.derived_from_evidence_ids
                    ),
                    "derivation_method": trace.mechanistic_bridge.derivation_method,
                    "distinct_from_retrieval_features": list(
                        trace.mechanistic_bridge.distinct_from_retrieval_features
                    ),
                    "is_narrower_than_retrieval": (
                        trace.mechanistic_bridge.is_narrower_than_retrieval
                    ),
                }
                if trace.mechanistic_bridge
                else None
            ),
            "final_relationship_class": trace.final_relationship_class.value,
            "final_rationale": trace.final_rationale,
            "actionable": trace.actionable,
            "search_coverage": coverage,
            "source_version": anchor["source_version"],
            "software_commit": software_commit,
            "pipeline_version": trace.pipeline_version,
            "review_status": ReviewStatus.AWAITING_EXPERT_SIGNOFF.value,
        }
        (traces_dir / f"{pair_id}.json").write_text(
            json.dumps(trace_payload, indent=2) + "\n", encoding="utf-8"
        )

        row = {
            "pair_id": pair_id,
            "retrieval_rank": ranks.get(name),
            "retrieval_axes": len(candidate.methods),
            "retrieval_information": candidate.total_information,
            "disease_a_id": anchor["disease_id"],
            "disease_a": anchor["disease_name"],
            "disease_b_id": other["disease_id"],
            "disease_b": other["disease_name"],
            "retrieval_reason": [r.reason_type.value for r in reasons],
            "retrieval_primary_feature": reasons[0].source_feature if reasons else None,
            "identity_class": identity.relation.value,
            "retrieval_validity": trace.retrieval_validity.value,
            "final_relationship": trace.final_relationship_class.value,
            "evidence_ids": list(trace.supporting_evidence_ids),
            "contradiction_ids": list(trace.contradicting_evidence_ids),
            "variant_compatibility": trace.variant_compatibility.value,
            "decision_trace_id": pair_id,
            "actionable": trace.actionable,
            "is_independent_discovery": relationship.is_independent_discovery,
            "review_status": ReviewStatus.AWAITING_EXPERT_SIGNOFF.value,
            "algorithm_version": trace.pipeline_version,
            "source_version": anchor["source_version"],
            "software_commit": software_commit,
        }

        negative = (
            trace.final_relationship_class in NEGATIVE_CLASSES
            or trace.final_relationship_class is RelationshipClass.INSUFFICIENT_EVIDENCE
        )
        if negative:
            rejected.append(
                {
                    **row,
                    "rejection": RejectedCrossDiseaseCandidate(
                        rejection_id=f"rejected:{pair_id}",
                        disease_a=anchor["disease_id"],
                        disease_b=other["disease_id"],
                        retrieval_reason_ids=tuple(
                            r.retrieval_reason_id for r in reasons
                        ),
                        rejected_class=trace.final_relationship_class,
                        retrieval_validity=trace.retrieval_validity,
                        reason=trace.final_rationale,
                        null_searches=(f"{query} -> {coverage.get('total_hits', 'n/a')} hits",),
                    ).model_dump(mode="json"),
                }
            )
        else:
            relationships.append(row)

        summary.append(
            {
                "rank": ranks.get(name),
                "pair": name,
                "identity": identity.relation.value,
                "relationship": trace.final_relationship_class.value,
                "retrieval_validity": trace.retrieval_validity.value,
                "anchored": trace.molecular_anchor_present,
                "evidence": len(evidence),
                "direct_primary": sum(
                    1 for e in evidence if e.establishes_direct_link and e.is_primary_finding
                ),
                "independent_discovery": relationship.is_independent_discovery,
                "identity_excluded": trace.final_relationship_class in IDENTITY_CLASSES,
            }
        )

    def write_jsonl(path: Path, rows: list[dict]) -> None:
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )

    write_jsonl(args.out / "relationships.jsonl", relationships)
    write_jsonl(args.out / "rejected_candidates.jsonl", rejected)
    (args.out / "goal1_candidates.json").write_text(
        json.dumps({
            "anchor": anchor["disease_name"],
            "anchor_id": anchor["disease_id"],
            "candidates_retrieved": len(retrieved),
            "candidates_evaluated": len(pair_names),
            "software_commit": software_commit,
            "ranked": [
                {
                    "rank": position + 1,
                    "disease_id": item.disease_id,
                    "disease_name": item.disease_name,
                    "axes": sorted(item.methods),
                    "total_information": item.total_information,
                    "per_axis": item.scores,
                    "top_features": [
                        {"label": feature.label, "class": feature.feature_class,
                         "corpus_frequency": feature.corpus_frequency,
                         "information_content": feature.information_content}
                        for feature in item.top_features(5)
                    ],
                }
                for position, item in enumerate(retrieved[:20])
            ],
            "evaluated": summary,
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"pairs": summary, "relationships": len(relationships),
                      "rejected": len(rejected)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
