"""Targeted capability discovery for unmet experiment requirements.

Two query tiers, kept explicitly distinct because they answer different questions:

* **Tier A, disease-anchored** — gene or disease plus the capability. Finds groups
  already working on this disease. High precision, very low recall: for an unmet
  requirement the combination is close to empty by definition, because it
  describes the experiment nobody has run yet.
* **Tier B, capability-anchored** — the capability plus the model context the
  experiment needs, *without* the gene. Finds groups who could do the work. This
  is the tier that matters for a missing capability; anchoring on the disease
  would only ever return people who already did the experiment.

A Tier B result evidences a technique in a comparable model system, never
involvement in this disease. That distinction is carried on every signal and
candidate, so a technique match can never be read as disease expertise.

Only the queries defined here are executed. The full generated query set is
recorded in the bundle but deliberately not run wholesale: most combinations are
redundant, and running them would inflate apparent coverage without adding
evidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from atlas.adapters.literature.client import (
    PubMedClient,
    PubMedRecord,
    RetrievalError,
    clean_affiliation,
)
from atlas.domain.discovery import CapabilityEvidenceSignal


class QueryTier(StrEnum):
    DISEASE_ANCHORED = "A_disease_anchored"
    CAPABILITY_ANCHORED = "B_capability_anchored"


@dataclass(frozen=True, slots=True)
class TargetedQuery:
    capability_category: str
    tier: QueryTier
    query: str
    rationale: str
    model_context: str
    # True when a hit demonstrates the technique in a model system comparable to the
    # one the experiment needs. False for Tier A probes that only confirm absence.
    model_system_match: bool = True


@dataclass(frozen=True, slots=True)
class CapabilityCandidate:
    """A publication-derived group that may be able to supply one capability."""

    candidate_id: str
    capability_category: str
    tier: QueryTier
    pmid: str
    title: str
    year: int | None
    last_author: str
    affiliation: str | None
    snapshot_sha256: str
    query: str
    disease_involvement: str
    limitation: str


@dataclass(frozen=True, slots=True)
class CapabilitySearchResult:
    query: TargetedQuery
    total_hits: int
    pmids: tuple[str, ...]
    snapshot_sha256: str


# The two decisive unmet capabilities get both tiers; the rest get one probe each.
TARGETED_QUERIES: tuple[TargetedQuery, ...] = (
    TargetedQuery(
        capability_category="crispr_editing",
        tier=QueryTier.DISEASE_ANCHORED,
        query=(
            '"STUB1"[tiab] AND ("knock-in"[tiab] OR "knockin"[tiab] OR isogenic[tiab] '
            'OR CRISPR[tiab]) AND (iPSC[tiab] OR "induced pluripotent"[tiab])'
        ),
        rationale="Has anyone edited the STUB1 locus in an iPSC background?",
        model_context="human iPSC",
    ),
    TargetedQuery(
        capability_category="crispr_editing",
        tier=QueryTier.CAPABILITY_ANCHORED,
        query=(
            "(isogenic[tiab] AND (\"knock-in\"[tiab] OR knockin[tiab] OR "
            '"base editing"[tiab] OR "prime editing"[tiab])) AND (iPSC[tiab] OR '
            '"induced pluripotent"[tiab]) AND (neuron*[tiab] OR cerebell*[tiab])'
        ),
        rationale=(
            "Who performs allele-specific endogenous editing in iPSC-derived neuronal "
            "systems, irrespective of gene?"
        ),
        model_context="isogenic iPSC-derived neurons",
    ),
    TargetedQuery(
        capability_category="isogenic_line_generation",
        tier=QueryTier.CAPABILITY_ANCHORED,
        query=(
            'isogenic[tiab] AND (iPSC[tiab] OR "induced pluripotent"[tiab]) AND '
            '("point mutation"[tiab] OR "single nucleotide"[tiab] OR variant*[tiab]) '
            "AND (neuron*[tiab] OR cerebell*[tiab])"
        ),
        rationale="Who generates isogenic variant panels in neuronal iPSC models?",
        model_context="isogenic iPSC variant panels",
    ),
    TargetedQuery(
        capability_category="proteomics",
        tier=QueryTier.DISEASE_ANCHORED,
        query=(
            '"STUB1"[tiab] AND ("diGly"[tiab] OR "ubiquitinome"[tiab] OR '
            '"ubiquitylome"[tiab])'
        ),
        rationale="Has a STUB1 substrate ubiquitinome ever been measured?",
        model_context="any",
        model_system_match=False,
    ),
    TargetedQuery(
        capability_category="proteomics",
        tier=QueryTier.CAPABILITY_ANCHORED,
        query=(
            '("diGly"[tiab] OR "ubiquitinome"[tiab] OR "ubiquitylome"[tiab] OR '
            '"ubiquitin remnant"[tiab]) AND (neuron*[tiab] OR iPSC[tiab] OR '
            '"induced pluripotent"[tiab] OR cerebell*[tiab])'
        ),
        rationale=(
            "Who runs diGly-enriched ubiquitinome proteomics on neuronal material, "
            "irrespective of gene?"
        ),
        model_context="neuronal diGly ubiquitinome",
    ),
    TargetedQuery(
        capability_category="ipsc_neuronal_differentiation",
        tier=QueryTier.CAPABILITY_ANCHORED,
        query=(
            '(iPSC[tiab] OR "induced pluripotent"[tiab]) AND (Purkinje[tiab] OR '
            "cerebellar[tiab]) AND (differentiat*[tiab] OR organoid[tiab])"
        ),
        rationale=(
            "Who differentiates iPSC to cerebellar or Purkinje-like neurons, the "
            "disease-relevant cell type?"
        ),
        model_context="cerebellar iPSC differentiation",
    ),
    TargetedQuery(
        capability_category="statistical_analysis",
        tier=QueryTier.CAPABILITY_ANCHORED,
        query=(
            '(iPSC[tiab] OR "induced pluripotent"[tiab]) AND (clone*[tiab] AND '
            '("mixed model"[tiab] OR "random effect*"[tiab] OR "variance component*"[tiab]))'
        ),
        rationale="Who applies clone-aware statistical models to iPSC experiments?",
        model_context="clone-level random-effects analysis",
    ),
)


def _affiliation(record: PubMedRecord) -> str | None:
    if not record.authors:
        return None
    for author in reversed(record.authors):
        if author.affiliations:
            return clean_affiliation(author.affiliations[0]) or None
    return None


def _candidate_id(pmid: str, capability_category: str) -> str:
    return f"capability-candidate:{capability_category}:PMID-{pmid}"


def run_searches(
    client: PubMedClient,
    queries: Sequence[TargetedQuery] = TARGETED_QUERIES,
    *,
    retmax: int = 15,
) -> tuple[tuple[CapabilitySearchResult, ...], tuple[str, ...]]:
    """Execute the targeted queries. Returns results and any failure messages."""
    results: list[CapabilitySearchResult] = []
    failures: list[str] = []
    for query in queries:
        try:
            total, pmids, digest = client.search(query.query, retmax=retmax)
        except RetrievalError as error:
            failures.append(f"{query.capability_category}/{query.tier.value}: {error}")
            continue
        results.append(
            CapabilitySearchResult(
                query=query,
                total_hits=total,
                pmids=tuple(pmids),
                snapshot_sha256=digest,
            )
        )
    return tuple(results), tuple(failures)


def derive_candidates(
    results: Sequence[CapabilitySearchResult],
    records: Mapping[str, PubMedRecord],
    *,
    per_capability: int = 3,
    exclude_pmids: frozenset[str] = frozenset(),
) -> tuple[CapabilityCandidate, ...]:
    """Derive candidate groups, newest first, capped per capability.

    ``exclude_pmids`` drops publications already represented by an existing
    candidate team, so the same group is not counted twice as a fresh lead.
    """
    by_capability: dict[str, list[CapabilityCandidate]] = {}
    seen: set[tuple[str, str]] = set()
    for result in results:
        for pmid in result.pmids:
            record = records.get(pmid)
            if record is None or not record.authors:
                continue
            if pmid in exclude_pmids:
                continue
            key = (result.query.capability_category, pmid)
            if key in seen:
                continue
            seen.add(key)
            disease = (
                "STUB1 or SCAR16 named in the title or abstract"
                if result.query.tier is QueryTier.DISEASE_ANCHORED
                else "no STUB1 or SCAR16 involvement established by this search"
            )
            limitation = (
                "Technique demonstrated in a comparable model system. This is not "
                "evidence of disease involvement, current activity, availability or "
                "willingness to collaborate."
                if result.query.tier is QueryTier.CAPABILITY_ANCHORED
                else "Disease-anchored hit; scope of the demonstrated technique still "
                "requires verification."
            )
            by_capability.setdefault(result.query.capability_category, []).append(
                CapabilityCandidate(
                    candidate_id=_candidate_id(pmid, result.query.capability_category),
                    capability_category=result.query.capability_category,
                    tier=result.query.tier,
                    pmid=pmid,
                    title=record.title,
                    year=record.year,
                    last_author=record.authors[-1].name,
                    affiliation=_affiliation(record),
                    snapshot_sha256=record.snapshot_sha256,
                    query=result.query.query,
                    disease_involvement=disease,
                    limitation=limitation,
                )
            )
    selected: list[CapabilityCandidate] = []
    for capability in sorted(by_capability):
        ordered = sorted(
            by_capability[capability],
            key=lambda item: (-(item.year or 0), item.pmid),
        )
        selected.extend(ordered[:per_capability])
    return tuple(selected)


def candidate_signals(
    candidates: Sequence[CapabilityCandidate],
    queries: Sequence[TargetedQuery] = TARGETED_QUERIES,
) -> dict[str, tuple[CapabilityEvidenceSignal, ...]]:
    """Build capability signals per candidate, keyed by candidate id.

    ``model_system_match`` follows the query's declared model context, so a probe
    that was not run in a comparable system cannot support a capability claim.
    """
    by_query = {(item.capability_category, item.query): item for item in queries}
    signals: dict[str, tuple[CapabilityEvidenceSignal, ...]] = {}
    for candidate in candidates:
        query = by_query.get((candidate.capability_category, candidate.query))
        model_match = query.model_system_match if query else True
        signals[candidate.candidate_id] = (
            CapabilityEvidenceSignal(
                evidence_id=f"PMID:{candidate.pmid}",
                source_type="publication",
                subject_scope="team",
                explicitly_demonstrates=True,
                # The capability is a technique: the context that matters is the model
                # system, not the disease. Disease involvement is tracked separately.
                biological_context_match=model_match,
                model_system_match=model_match,
                active=None,
                publication_year=candidate.year,
                exact_support=candidate.title,
                source_url=f"https://pubmed.ncbi.nlm.nih.gov/{candidate.pmid}/",
            ),
        )
    return signals


def coverage_note(results: Sequence[CapabilitySearchResult]) -> str:
    by_tier: dict[str, list[str]] = {}
    for result in results:
        by_tier.setdefault(result.query.tier.value, []).append(
            f"{result.query.capability_category}={result.total_hits}"
        )
    parts = [f"{tier}: {', '.join(sorted(items))}" for tier, items in sorted(by_tier.items())]
    return (
        "Targeted capability queries executed (a deliberately small, deduplicated "
        "subset of the generated set). " + "; ".join(parts)
    )


def recency_window(as_of: date, years: int = 5) -> int:
    return as_of.year - years
