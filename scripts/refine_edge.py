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
from atlas.adapters.literature.resolver import (
    Resolution,
    canonical_identity,
    resolve_reference,
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

UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"

# Disease-specific settings come from the plan, not from this module: the runner
# must work for any DisMech edge. A plan supplies target.uniprot and a
# coverage_queries map; the SCAR16 plan's values are not defaults for others.


def uniprot_url(accession: str) -> str:
    return f"{UNIPROT_BASE}/{accession}.json"


def _edge_index(path: str) -> tuple[int, int]:
    numbers = [int(value) for value in re.findall(r"\[(\d+)\]", path)]
    if len(numbers) != 2:
        raise SystemExit(f"edge_path must look like pathophysiology[i].downstream[j]: {path!r}")
    return numbers[0], numbers[1]


def _evidence_by_path(imported: ImportedDisease) -> dict[str, EvidenceItem]:
    return {item.provenance.source_object_path: item for item in imported.evidence}


def _uniprot_features(
    fetcher: SnapshotFetcher, accession: str
) -> tuple[tuple[tuple[str, int, int, str], ...], str | None]:
    """Return domain features and, on failure, the reason.

    Protein-domain context is optional: it is derived context, not evidence. An
    outage must therefore degrade to "no domains derived" and be recorded as a
    failed source, never abort a refinement run or be silently replaced.
    """
    try:
        payload, _ = fetch_json(fetcher, uniprot_url(accession))
    except RetrievalError as error:
        return (), str(error)
    features: list[tuple[str, int, int, str]] = []
    for feature in payload.get("features", []):
        location = feature.get("location", {})
        start = location.get("start", {}).get("value")
        end = location.get("end", {}).get("value")
        if isinstance(start, int) and isinstance(end, int):
            features.append(
                (str(feature.get("type")), start, end, str(feature.get("description") or ""))
            )
    return tuple(features), None


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

    accession = str(target["uniprot"])
    features, uniprot_error = _uniprot_features(fetcher, accession)

    # Resolve every source key to an imported EvidenceItem (upstream) or a
    # retrieved-only identifier, and collect its cached text.
    sources_meta: dict[str, dict[str, Any]] = plan["sources"]
    texts: dict[str, tuple[SourceText, ...]] = {}
    titles: dict[str, str | None] = {}
    evidence_for_key: dict[str, EvidenceItem | None] = {}
    resolutions: dict[str, Resolution] = {}
    canonical: dict[str, str | None] = {}
    coverage_rows: list[SearchSourceCoverage] = []
    for key, meta in sources_meta.items():
        declared = meta.get("pmid")
        # An upstream reference that is not a PMID (a bare PMC or publisher URL, an
        # ORPHA code) cannot be deterministically resolved. The plan may record a
        # resolved_pmid so the text can still be retrieved for context, but the
        # declared identifier must match what upstream actually wrote.
        resolved = meta.get("resolved_pmid")
        pmcid = meta.get("pmcid")
        if key.startswith("upstream:"):
            path = key.split(":", 1)[1]
            item = evidence_by_path.get(path)
            if item is None:
                raise SystemExit(f"source key {key} does not match an imported evidence path")
            expected = f"PMID:{declared}" if declared else None
            if item.pmid != expected:
                raise SystemExit(
                    f"source key {key} declares {expected} but upstream has {item.pmid}"
                )
            evidence_for_key[key] = item
        else:
            evidence_for_key[key] = None
        # Canonical identity for independence counting. The upstream form is kept
        # separately; resolution never rewrites what upstream wrote.
        upstream_form = (
            str(meta.get("upstream_reference_form"))
            if meta.get("upstream_reference_form")
            else (f"PMID:{declared}" if declared else "")
        )
        resolution = resolve_reference(upstream_form or f"PMID:{declared}", fetcher)
        resolutions[key] = resolution
        canonical[key] = (
            resolution.canonical
            or (f"PMID:{resolved}" if resolved else None)
            or canonical_identity(upstream_form, resolution)
        )
        fetch_pmid = declared or resolved
        if not fetch_pmid:
            texts[key], titles[key] = (), None
            continue
        try:
            texts[key], titles[key] = _source_texts(
                str(fetch_pmid), pmcid, pubmed, europepmc
            )
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
            cell_type_scope=tuple(spec.get("cell_type_scope") or ()),
            readout_scope=tuple(spec.get("readout_scope") or ()),
        )
        for spec in plan["atomic_claims"]
    }

    observations = []
    for entry in observations_doc["observations"]:
        key = entry["source"]
        item = evidence_for_key[key]
        identifier = (
            f"PMID:{sources_meta[key]['pmid']}"
            if sources_meta[key].get("pmid")
            else str(
                sources_meta[key].get("upstream_reference_form")
                or (item.other_reference if item is not None else "unknown-reference")
            )
        )
        observations.append(
            build_observation(
                entry,
                evidence_id=(
                    item.evidence_id if item is not None else f"retrieved:{identifier}"
                ),
                source_identifier=canonical.get(key) or identifier,
                upstream_reference_form=identifier,
                gene=target["gene"],
                sources=texts[key],
                uniprot_features=features,
                upstream_snippet=item.exact_supported_span if item is not None else None,
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
        checks.append(
            verify_citation(
                item,
                resolved_title=resolved_title,
                sources=source_texts,
                canonical_identifier=canonical.get(match_key) if match_key else None,
            )
        )
    observation_checks: dict[str, Any] = {}
    for observation, entry in zip(observations, observations_doc["observations"], strict=True):
        key = entry["source"]
        item = evidence_for_key[key]
        pmid = str(sources_meta[key].get("pmid") or "")
        if item is not None:
            probe = item.model_copy(
                update={"exact_supported_span": observation.support_span}
            )
        else:
            probe = EvidenceItem(
                evidence_id=observation.evidence_id,
                claim_id=upstream_claim.claim_id,
                pmid=pmid or None,
                other_reference=None if pmid else observation.source_identifier,
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
            probe,
            resolved_title=titles.get(key),
            sources=texts[key],
            canonical_identifier=canonical.get(key),
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
    queries_to_run: dict[str, str] = dict(plan.get("coverage_queries") or {})
    if not queries_to_run:
        raise SystemExit(
            "the plan must declare coverage_queries: literature coverage cannot be "
            "inherited from another disease"
        )
    for name, query in queries_to_run.items():
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
            source=f"UniProt {accession} (domain boundaries)",
            status=(
                CoverageStatus.FAILED if uniprot_error else CoverageStatus.CHECKED
            ),
            queries=(uniprot_url(accession),),
            checked_at=None if uniprot_error else now,
            result_count=None if uniprot_error else len(features),
            error=uniprot_error,
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
