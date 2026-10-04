#!/usr/bin/env python3
"""Refine one real DisMech mechanism edge end to end.

Pipeline: import the upstream entry -> collect the edge's upstream evidence ->
resolve extractor locators against cached source snapshots -> deterministically
verify citations and quoted spans -> run the independent rule-based critic per
claim/observation pair -> synthesize categorical statuses -> write the run
artifact plus a search-coverage record.

The critic is deterministic and rule-based: no LLM API key is configured in this
environment, so no model adjudication takes place. It is not human review.

Network use: all external reads go through the snapshot cache. Pass --offline to
require cache hits only (the default for reproducing a recorded run).
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atlas.adapters.dismech import DisMechImporter
from atlas.adapters.dismech.importer import ImportedDisease
from atlas.adapters.literature.client import (
    EuropePMCClient,
    PubMedClient,
    RetrievalError,
    SnapshotFetcher,
    fetch_json,
)
from atlas.domain.claims import Claim, RefinementStatus
from atlas.domain.evidence import (
    CitationStatus,
    EvidenceItem,
    EvidenceModality,
    EvidenceOrigin,
    EvidenceRelation,
)
from atlas.domain.gaps import (
    CoverageStatus,
    SearchCoverage,
    SearchSourceCoverage,
)
from atlas.domain.refinement import AtomicClaimSpec, EdgeRefinement, EffectDirection
from atlas.services import evidence_critic
from atlas.services.citation_validation import SourceText, verify_citation
from atlas.services.extraction_build import build_observation
from atlas.services.refinement import (
    derived_provenance,
    synthesize_claim,
    synthesize_edge,
)

UNIPROT_URL = "https://rest.uniprot.org/uniprotkb/Q9UNE7.json"

# Literature queries executed for this edge. Kept here so coverage records the
# exact query text that produced the retrieved evidence.
QUERIES: dict[str, str] = {
    "pm_allele": (
        "(STUB1[tiab] OR CHIP[tiab]) AND (E28K[tiab] OR K145Q[tiab] OR M211I[tiab] OR "
        "S236T[tiab] OR N65S[tiab] OR T246M[tiab] OR Lys145Gln[tiab] OR Met211Ile[tiab] OR "
        "Glu28Lys[tiab] OR Ser236Thr[tiab])"
    ),
    "pm_function": (
        'STUB1[tiab] AND (SCAR16[tiab] OR "spinocerebellar ataxia"[tiab] OR '
        '"Gordon Holmes"[tiab]) AND (ubiquitin*[tiab] OR "E3 ligase"[tiab] OR '
        '"ligase activity"[tiab])'
    ),
    "pm_sca48": (
        'STUB1[tiab] AND (SCA48[tiab] OR "spinocerebellar ataxia 48"[tiab] OR '
        '"spinocerebellar ataxia type 48"[tiab])'
    ),
    "pm_models": (
        'STUB1[tiab] AND ataxia[tiab] AND (iPSC[tiab] OR "induced pluripotent"[tiab] OR '
        "neurons[tiab] OR fibroblasts[tiab] OR mice[tiab] OR rats[tiab] OR zebrafish[tiab])"
    ),
    "pm_negative": (
        '(STUB1[tiab] OR CHIP[tiab]) AND (SCAR16[tiab] OR SCA48[tiab]) AND ("retain*"[tiab] '
        'OR "preserved"[tiab] OR "not affect*"[tiab] OR "dominant negative"[tiab] OR '
        '"gain of function"[tiab] OR "toxic"[tiab])'
    ),
}


def _edge_index(path: str) -> tuple[int, int]:
    numbers = [int(value) for value in re.findall(r"\[(\d+)\]", path)]
    if len(numbers) != 2:
        raise SystemExit(f"edge_path must look like pathophysiology[i].downstream[j]: {path!r}")
    return numbers[0], numbers[1]


def _evidence_by_path(imported: ImportedDisease) -> dict[str, EvidenceItem]:
    return {item.provenance.source_object_path: item for item in imported.evidence}


def _uniprot_features(fetcher: SnapshotFetcher) -> tuple[tuple[str, int, int, str], ...]:
    payload, _ = fetch_json(fetcher, UNIPROT_URL)
    features: list[tuple[str, int, int, str]] = []
    for feature in payload.get("features", []):
        location = feature.get("location", {})
        start = location.get("start", {}).get("value")
        end = location.get("end", {}).get("value")
        if isinstance(start, int) and isinstance(end, int):
            features.append(
                (str(feature.get("type")), start, end, str(feature.get("description") or ""))
            )
    return tuple(features)


def _source_texts(
    pmid: str,
    pmcid: str | None,
    pubmed: PubMedClient,
    europepmc: EuropePMCClient,
) -> tuple[tuple[SourceText, ...], str | None]:
    records = pubmed.records((pmid,))
    record = records.get(pmid)
    if record is None:
        return (), None
    sources = [
        SourceText("title", record.title, record.snapshot_sha256),
        SourceText("abstract", record.abstract, record.snapshot_sha256),
    ]
    if pmcid:
        full = europepmc.full_text(pmcid)
        if full is not None:
            sources.append(SourceText("full_text", full[0], full[1]))
    return tuple(sources), record.title


def run(plan_dir: Path, *, offline: bool, output: Path) -> int:
    plan = json.loads((plan_dir / "observation_plan.json").read_text())
    observations_doc = json.loads((plan_dir / "observations.json").read_text())
    target = plan["target"]
    fetcher = SnapshotFetcher(plan_dir / "snapshots", offline=offline)
    pubmed = PubMedClient(fetcher)
    europepmc = EuropePMCClient(fetcher)

    source_path = Path(target["disease_file"])
    importer = DisMechImporter(source_version=target["dismech_commit"])
    imported = importer.load_path(source_path)
    _edge_index(target["edge_path"])
    edge_path = target["edge_path"]
    edges = [edge for edge in imported.graph.edges if edge.provenance.source_object_path == edge_path]
    if not edges:
        raise SystemExit(f"edge {edge_path} not found in {source_path}")
    edge = edges[0]
    upstream_claim = next(item for item in imported.claims if item.claim_id == edge.claim_id)
    evidence_by_path = _evidence_by_path(imported)
    upstream_edge_evidence = tuple(
        item for item in imported.evidence if item.claim_id == edge.claim_id
    )

    features = _uniprot_features(fetcher)

    # Resolve every source key to an imported EvidenceItem (upstream) or a
    # retrieved-only identifier, and collect its cached text.
    sources_meta: dict[str, dict[str, Any]] = plan["sources"]
    texts: dict[str, tuple[SourceText, ...]] = {}
    titles: dict[str, str | None] = {}
    evidence_for_key: dict[str, EvidenceItem | None] = {}
    coverage_rows: list[SearchSourceCoverage] = []
    for key, meta in sources_meta.items():
        pmid = str(meta["pmid"])
        pmcid = meta.get("pmcid")
        if key.startswith("upstream:"):
            path = key.split(":", 1)[1]
            item = evidence_by_path.get(path)
            if item is None:
                raise SystemExit(f"source key {key} does not match an imported evidence path")
            if item.pmid != f"PMID:{pmid}":
                raise SystemExit(
                    f"source key {key} declares PMID:{pmid} but upstream has {item.pmid}"
                )
            evidence_for_key[key] = item
        else:
            evidence_for_key[key] = None
        try:
            texts[key], titles[key] = _source_texts(pmid, pmcid, pubmed, europepmc)
        except RetrievalError as exc:
            raise SystemExit(f"retrieval failed for {key}: {exc}") from exc

    claim_specs = {
        spec["claim_id"]: AtomicClaimSpec(
            claim_id=spec["claim_id"],
            statement=spec["statement"],
            gene=target["gene"],
            disease_scope=tuple(target["disease_scope"]),
            variant_scope=tuple(spec["variant_scope"]),
            scope_class=spec["scope_class"],
            readout_family=tuple(plan["readout_family"]),
            expected_effect=(EffectDirection.ABOLISHED, EffectDirection.DECREASED),
        )
        for spec in plan["atomic_claims"]
    }

    observations = []
    for entry in observations_doc["observations"]:
        key = entry["source"]
        item = evidence_for_key[key]
        pmid = str(sources_meta[key]["pmid"])
        observations.append(
            build_observation(
                entry,
                evidence_id=item.evidence_id if item is not None else f"retrieved:PMID:{pmid}",
                source_identifier=f"PMID:{pmid}",
                gene=target["gene"],
                sources=texts[key],
                uniprot_features=features,
            )
        )

    # Deterministic citation checks: upstream evidence items for this edge, plus
    # each observation's own span against the text it was taken from.
    checks = []
    for item in upstream_edge_evidence:
        match_key = next(
            (
                candidate
                for candidate, value in evidence_for_key.items()
                if value is not None and value.evidence_id == item.evidence_id
            ),
            None,
        )
        source_texts: tuple[SourceText, ...] = texts.get(match_key, ()) if match_key else ()
        resolved_title: str | None = titles.get(match_key) if match_key else None
        checks.append(verify_citation(item, resolved_title=resolved_title, sources=source_texts))
    observation_checks: dict[str, Any] = {}
    for observation, entry in zip(observations, observations_doc["observations"], strict=True):
        key = entry["source"]
        item = evidence_for_key[key]
        pmid = str(sources_meta[key]["pmid"])
        if item is not None:
            probe = item.model_copy(
                update={"exact_supported_span": observation.support_span}
            )
        else:
            probe = EvidenceItem(
                evidence_id=observation.evidence_id,
                claim_id=upstream_claim.claim_id,
                pmid=pmid,
                title=titles.get(key),
                exact_supported_span=observation.support_span,
                evidence_relation=EvidenceRelation.NEUTRAL,
                evidence_origin=EvidenceOrigin.PRIMARY_RESULT,
                evidence_modality=EvidenceModality.OTHER,
                retrieval_date=importer.retrieval_date,
                provenance=derived_provenance(
                    upstream_claim.provenance, method="retrieved_contradiction_search"
                ),
            )
        observation_checks[observation.observation_id] = verify_citation(
            probe, resolved_title=titles.get(key), sources=texts[key]
        )

    reviews = []
    for observation in observations:
        for claim_id in observation.claim_ids:
            spec = claim_specs.get(claim_id)
            if spec is None:
                raise SystemExit(f"observation {observation.observation_id} cites unknown {claim_id}")
            reviews.append(
                evidence_critic.review(
                    spec, observation, observation_checks[observation.observation_id]
                )
            )

    provenance = derived_provenance(
        upstream_claim.provenance,
        method="structured_decomposition_v1",
        payload={"edge_path": edge_path, "plan": "observation_plan.json"},
    )
    atomic = [
        synthesize_claim(
            spec, reviews, observations, upstream=upstream_claim, provenance=provenance
        )
        for spec in claim_specs.values()
    ]
    status, rule, rationale = synthesize_edge(atomic)

    now = datetime.now(UTC)
    for name, query in QUERIES.items():
        try:
            count, _ids, _ = pubmed.search(query, retmax=100)
            coverage_rows.append(
                SearchSourceCoverage(
                    source=f"PubMed ({name})",
                    status=CoverageStatus.CHECKED,
                    queries=(query,),
                    checked_at=now,
                    result_count=count,
                )
            )
        except RetrievalError as exc:
            coverage_rows.append(
                SearchSourceCoverage(
                    source=f"PubMed ({name})",
                    status=CoverageStatus.FAILED,
                    queries=(query,),
                    error=str(exc),
                )
            )
    coverage_rows.append(
        SearchSourceCoverage(
            source="Europe PMC full text",
            status=CoverageStatus.CHECKED,
            queries=("per-PMID open-access full text retrieval",),
            checked_at=now,
            result_count=sum(
                1 for items in texts.values() if any(s.location == "full_text" for s in items)
            ),
        )
    )
    coverage_rows.append(
        SearchSourceCoverage(
            source="UniProt Q9UNE7 (domain boundaries)",
            status=CoverageStatus.CHECKED,
            queries=(UNIPROT_URL,),
            checked_at=now,
            result_count=len(features),
        )
    )
    coverage = SearchCoverage(
        coverage_id=f"coverage:{edge.id}",
        sources=tuple(coverage_rows),
        search_completed_at=now,
    )

    refinement = EdgeRefinement(
        run_id=f"refine:{edge.id}",
        upstream_claim=upstream_claim,
        upstream_edge_id=edge.id,
        upstream_evidence_ids=tuple(item.evidence_id for item in upstream_edge_evidence),
        upstream_context_evidence_ids=tuple(
            item.evidence_id
            for item in imported.evidence
            if item.claim_id != edge.claim_id
            and item.evidence_id in {obs.evidence_id for obs in observations}
        ),
        citation_checks=tuple(checks) + tuple(observation_checks.values()),
        observations=tuple(observations),
        reviews=tuple(reviews),
        atomic=tuple(atomic),
        edge_status=status,
        edge_rule_applied=rule,
        edge_rationale=rationale,
        recommended_scope=_recommended_scope(atomic),
        search_coverage=coverage,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(refinement.model_dump_json(indent=2), encoding="utf-8")
    _report(imported, refinement, upstream_claim)
    return 0


def _recommended_scope(atomic: Sequence[Any]) -> str:
    supported = [
        item.claim.normalized_statement
        for item in atomic
        if item.status is RefinementStatus.SUPPORTED
    ]
    other = [
        f"{item.claim.normalized_statement} [{item.status.value}]"
        for item in atomic
        if item.status is not RefinementStatus.SUPPORTED
    ]
    parts = []
    if supported:
        parts.append("Licensed by the evidence: " + "; ".join(supported))
    if other:
        parts.append("Not licensed as stated: " + "; ".join(other))
    return " || ".join(parts)


def _report(imported: ImportedDisease, refinement: EdgeRefinement, upstream: Claim) -> None:
    print(
        json.dumps(
            {
                "disease": imported.disease.canonical_name,
                "mondo": imported.disease.mondo_id,
                "upstream_edge": refinement.upstream_edge_id,
                "upstream_claim_statement": upstream.normalized_statement,
                "upstream_evidence_count": len(refinement.upstream_evidence_ids),
                "observations": len(refinement.observations),
                "reviews": len(refinement.reviews),
                "citation_checks": {
                    status.value: sum(
                        1 for check in refinement.citation_checks if check.status is status
                    )
                    for status in CitationStatus
                },
                "atomic": {
                    item.claim.normalized_statement: f"{item.status.value} (rule {item.rule_applied})"
                    for item in refinement.atomic
                },
                "edge_status": refinement.edge_status.value,
                "edge_rule": refinement.edge_rule_applied,
            },
            indent=2,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan_dir", type=Path)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return run(args.plan_dir, offline=args.offline, output=args.output)


if __name__ == "__main__":
    raise SystemExit(main())
