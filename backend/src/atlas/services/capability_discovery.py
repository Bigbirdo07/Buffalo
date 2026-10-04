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
class DiscoveryContext:
    """The scientific context a search is anchored to.

    Derived from the active disease, experiment and required capabilities, never
    written as literals. This is what makes the action engine reusable across
    diseases instead of working only for the one it was first written for.
    """

    gene_symbols: tuple[str, ...] = ()
    cell_type_terms: tuple[str, ...] = ()
    assay_terms: tuple[str, ...] = ()
    model_system_terms: tuple[str, ...] = ()
    disease_terms: tuple[str, ...] = ()

    @property
    def anchor_label(self) -> str:
        """How a disease-anchored hit should be described, in this run's terms."""
        anchors = [*self.gene_symbols, *self.disease_terms]
        return " or ".join(anchors) if anchors else "the disease or gene of interest"


@dataclass(frozen=True, slots=True)
class QueryTemplate:
    """A capability-generic query with slots filled from DiscoveryContext."""

    capability_category: str
    tier: QueryTier
    template: str
    rationale: str
    model_context: str
    model_system_match: bool = True
    # Slot names that must be non-empty for this template to be usable.
    requires: tuple[str, ...] = ()


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


# Query templates. These are capability-generic: each describes a laboratory
# skill, and disease specifics arrive through DiscoveryContext at call time.
#
# Previously this was a tuple of literal queries naming one gene and one cell
# type, which meant the action engine only worked for the disease it was written
# for. A template whose required slots cannot be filled is skipped rather than
# emitted with an empty term, because a query missing its anchor silently
# becomes a different, much broader question.
QUERY_TEMPLATES: tuple[QueryTemplate, ...] = (
    QueryTemplate(
        capability_category="crispr_editing",
        tier=QueryTier.DISEASE_ANCHORED,
        template=(
            '{gene} AND ("knock-in"[tiab] OR "knockin"[tiab] OR isogenic[tiab] '
            'OR CRISPR[tiab]) AND (iPSC[tiab] OR "induced pluripotent"[tiab])'
        ),
        rationale="Has anyone edited this locus in an iPSC background?",
        model_context="human iPSC",
        requires=("gene",),
    ),
    QueryTemplate(
        capability_category="crispr_editing",
        tier=QueryTier.CAPABILITY_ANCHORED,
        template=(
            '(isogenic[tiab] AND ("knock-in"[tiab] OR knockin[tiab] OR '
            '"base editing"[tiab] OR "prime editing"[tiab])) AND (iPSC[tiab] OR '
            '"induced pluripotent"[tiab]) AND {cell}'
        ),
        rationale=(
            "Who performs allele-specific endogenous editing in the relevant "
            "cellular system, irrespective of gene?"
        ),
        model_context="isogenic iPSC-derived cells",
        requires=("cell",),
    ),
    QueryTemplate(
        capability_category="isogenic_line_generation",
        tier=QueryTier.CAPABILITY_ANCHORED,
        template=(
            'isogenic[tiab] AND (iPSC[tiab] OR "induced pluripotent"[tiab]) AND '
            '("point mutation"[tiab] OR "single nucleotide"[tiab] OR variant*[tiab]) '
            "AND {cell}"
        ),
        rationale="Who generates isogenic variant panels in the relevant cell type?",
        model_context="isogenic iPSC variant panels",
        requires=("cell",),
    ),
    QueryTemplate(
        capability_category="proteomics",
        tier=QueryTier.DISEASE_ANCHORED,
        template='{gene} AND {assay}',
        rationale="Has the relevant molecular readout ever been measured for this gene?",
        model_context="any",
        model_system_match=False,
        requires=("gene", "assay"),
    ),
    QueryTemplate(
        capability_category="proteomics",
        tier=QueryTier.CAPABILITY_ANCHORED,
        template='{assay} AND ({cell} OR iPSC[tiab] OR "induced pluripotent"[tiab])',
        rationale=(
            "Who runs this molecular readout on disease-relevant material, "
            "irrespective of gene?"
        ),
        model_context="assay in relevant material",
        requires=("assay", "cell"),
    ),
    QueryTemplate(
        capability_category="ipsc_neuronal_differentiation",
        tier=QueryTier.CAPABILITY_ANCHORED,
        template=(
            '(iPSC[tiab] OR "induced pluripotent"[tiab]) AND {cell} AND '
            "(differentiat*[tiab] OR organoid[tiab])"
        ),
        rationale="Who differentiates iPSC to the disease-relevant cell type?",
        model_context="targeted iPSC differentiation",
        requires=("cell",),
    ),
    QueryTemplate(
        capability_category="statistical_analysis",
        tier=QueryTier.CAPABILITY_ANCHORED,
        template=(
            '(iPSC[tiab] OR "induced pluripotent"[tiab]) AND (clone*[tiab] AND '
            '("mixed model"[tiab] OR "random effect*"[tiab] OR "variance component*"[tiab]))'
        ),
        rationale="Who applies clone-aware statistical models to iPSC experiments?",
        model_context="clone-level random-effects analysis",
        requires=(),
    ),
)


def _or_group(terms: Sequence[str], field: str = "tiab") -> str:
    """Build a PubMed OR group, quoting multi-word terms."""
    parts = []
    for term in terms:
        cleaned = term.strip()
        if not cleaned:
            continue
        quoted = f'"{cleaned}"' if " " in cleaned or "-" in cleaned else cleaned
        parts.append(f"{quoted}[{field}]")
    if not parts:
        return ""
    return parts[0] if len(parts) == 1 else "(" + " OR ".join(parts) + ")"


def build_targeted_queries(
    context: DiscoveryContext,
    templates: Sequence[QueryTemplate] = QUERY_TEMPLATES,
) -> tuple[tuple[TargetedQuery, ...], tuple[str, ...]]:
    """Fill templates from the active scientific context.

    Returns the usable queries plus a note for every template that could not be
    filled, so a missing search is visible as missing rather than absent.
    """
    slots = {
        "gene": _or_group(context.gene_symbols),
        "cell": _or_group(context.cell_type_terms),
        "assay": _or_group(context.assay_terms),
        "model": _or_group(context.model_system_terms),
    }
    built: list[TargetedQuery] = []
    skipped: list[str] = []
    for template in templates:
        missing = [name for name in template.requires if not slots.get(name)]
        if missing:
            skipped.append(
                f"{template.capability_category}/{template.tier.value}: no "
                f"{', '.join(missing)} term available in context"
            )
            continue
        built.append(
            TargetedQuery(
                capability_category=template.capability_category,
                tier=template.tier,
                query=template.template.format(**slots),
                rationale=template.rationale,
                model_context=template.model_context,
                model_system_match=template.model_system_match,
            )
        )
    return tuple(built), tuple(skipped)


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
    queries: Sequence[TargetedQuery],
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
    anchor_label: str = "the disease or gene of interest",
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
                f"{anchor_label} named in the title or abstract"
                if result.query.tier is QueryTier.DISEASE_ANCHORED
                else f"no {anchor_label} involvement established by this search"
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
    queries: Sequence[TargetedQuery],
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
