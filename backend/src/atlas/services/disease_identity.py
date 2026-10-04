"""Decide whether two disease labels denote independent diseases.

This runs before any cross-disease claim. Two labels for one allelic spectrum
are a data-model question, not a discovery, and counting them as cross-disease
findings inflates novelty: the system would report "we connected two diseases"
when it had found two names for one.

The rule is general and uses only corpus-wide signals -- shared causal genes,
phenotype overlap measured against the ontology, and name morphology. It encodes
no disease, gene or pathway. Where upstream sources disagree or signals are
mixed, the answer is PARTIALLY_OVERLAPPING_ENTITY with a review flag rather than
an automatic merge, because collapsing two records is destructive and a curator
should make that call.

Deliberate asymmetry: the detector is tuned to *raise the question*, not to
settle it. A false ALLELIC_SPECTRUM flag costs a curator one review; a missed one
silently inflates every downstream discovery count.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from atlas.domain.cross_disease import (
    DiseaseIdentityRelationship,
    IdentityRelation,
    ReviewStatus,
)
from atlas.services.hpo_similarity import PhenotypeSimilarity

# Phenotype overlap, as a share of the smaller annotation set, above which two
# same-gene disorders look like one spectrum rather than two diseases.
STRONG_PHENOTYPE_OVERLAP = 0.5
MODERATE_PHENOTYPE_OVERLAP = 0.25

# Tokens that distinguish disease labels without implying different biology:
# inheritance mode, numbering and type designations routinely separate members of
# one allelic series.
_SERIES_TOKENS = re.compile(
    r"\b(type|subtype|form|variant|autosomal|recessive|dominant|"
    r"x[- ]?linked|early|late|infantile|juvenile|adult|onset|"
    r"[0-9]+[a-z]?|[ivx]+)\b",
    re.IGNORECASE,
)
_NOISE = re.compile(r"[^a-z0-9 ]+")


def _core_name(name: str) -> str:
    """Strip series designations so 'Ataxia Type 2' and 'Ataxia' compare equal."""
    lowered = _NOISE.sub(" ", name.lower())
    stripped = _SERIES_TOKENS.sub(" ", lowered)
    return " ".join(stripped.split())


@dataclass(frozen=True)
class IdentitySignals:
    """The observations behind a verdict, reported so it can be disputed."""

    shared_genes: tuple[str, ...]
    only_genes_a: tuple[str, ...]
    only_genes_b: tuple[str, ...]
    phenotype_overlap: float
    shared_phenotype_count: int
    name_core_match: bool
    same_mondo: bool

    @property
    def gene_sets_identical(self) -> bool:
        return bool(self.shared_genes) and not (self.only_genes_a or self.only_genes_b)

    @property
    def contained_gene_set(self) -> bool:
        """One disease's whole gene set sits inside the other's, not vice versa."""
        if not self.shared_genes or self.gene_sets_identical:
            return False
        return not self.only_genes_a or not self.only_genes_b


def compute_signals(
    left: dict,
    right: dict,
    similarity: PhenotypeSimilarity,
    left_phenotypes: frozenset[str],
    right_phenotypes: frozenset[str],
) -> IdentitySignals:
    genes_a = frozenset(left.get("gene_ids") or ())
    genes_b = frozenset(right.get("gene_ids") or ())
    shared_ph = left_phenotypes & right_phenotypes
    smaller = min(len(left_phenotypes), len(right_phenotypes)) or 1
    mondo_a, mondo_b = left.get("mondo_id"), right.get("mondo_id")
    return IdentitySignals(
        shared_genes=tuple(sorted(genes_a & genes_b)),
        only_genes_a=tuple(sorted(genes_a - genes_b)),
        only_genes_b=tuple(sorted(genes_b - genes_a)),
        phenotype_overlap=round(len(shared_ph) / smaller, 3),
        shared_phenotype_count=len(shared_ph),
        name_core_match=(
            _core_name(left["disease_name"]) == _core_name(right["disease_name"])
            and bool(_core_name(left["disease_name"]))
        ),
        same_mondo=bool(mondo_a) and mondo_a == mondo_b,
    )


def classify_identity(signals: IdentitySignals) -> tuple[IdentityRelation, str]:
    """Map signals to an identity relation and say why.

    Ordered from strongest evidence down. Every branch states its reasoning so a
    curator can disagree with the specific step rather than the whole verdict.
    """
    if signals.same_mondo:
        return (
            IdentityRelation.SAME_DISEASE,
            "Both records carry the same MONDO identifier, so upstream already "
            "treats them as one disease entity.",
        )

    if not signals.shared_genes:
        return (
            IdentityRelation.DISTINCT_DISEASE,
            "No shared causal gene, so these are independent disease entities and "
            "any relationship between them must be argued biologically.",
        )

    if signals.gene_sets_identical:
        if signals.phenotype_overlap >= STRONG_PHENOTYPE_OVERLAP:
            return (
                IdentityRelation.ALLELIC_SPECTRUM,
                f"Identical causal gene set ({', '.join(signals.shared_genes)}) and "
                f"{signals.phenotype_overlap:.0%} phenotype overlap. These labels "
                "most likely describe one allelic spectrum rather than two "
                "diseases; a relationship between them is not a cross-disease "
                "discovery.",
            )
        if signals.name_core_match:
            return (
                IdentityRelation.PHENOTYPIC_SUBTYPE,
                f"Identical causal gene set and disease names differing only by "
                "series designation (type, inheritance mode or number), with "
                f"{signals.phenotype_overlap:.0%} phenotype overlap. Likely "
                "subtypes of one entity presenting differently.",
            )
        return (
            IdentityRelation.PARTIALLY_OVERLAPPING_ENTITY,
            f"Identical causal gene set but only "
            f"{signals.phenotype_overlap:.0%} phenotype overlap. One gene can "
            "produce mechanistically distinct disorders, so this needs expert "
            "review rather than an automatic merge.",
        )

    # One disease's entire causal gene set contained in the other's is the
    # signature of a genetic subtype inside a broader, genetically heterogeneous
    # entity: the narrow label names one cause of the wide label. Treating that
    # as two independent diseases would count a subtype relationship as a
    # cross-disease discovery.
    if signals.contained_gene_set and signals.phenotype_overlap >= MODERATE_PHENOTYPE_OVERLAP:
        return (
            IdentityRelation.PARTIALLY_OVERLAPPING_ENTITY,
            f"One disease's complete causal gene set ({', '.join(signals.shared_genes)}) "
            "is contained in the other's, which also has additional causes. The "
            "narrower label is most likely a genetic subtype of the broader "
            "entity rather than an independent disease, so a relationship "
            "between them is not a cross-disease discovery without expert review.",
        )

    if signals.phenotype_overlap >= STRONG_PHENOTYPE_OVERLAP:
        return (
            IdentityRelation.PARTIALLY_OVERLAPPING_ENTITY,
            f"Partially shared genes ({', '.join(signals.shared_genes)}) with "
            f"{signals.phenotype_overlap:.0%} phenotype overlap. The entities "
            "overlap without being identical.",
        )

    return (
        IdentityRelation.DISTINCT_DISEASE,
        f"Shared gene ({', '.join(signals.shared_genes)}) but each disease also "
        "has distinct causal genes and phenotype overlap is limited. Independent "
        "diseases that happen to involve a common gene.",
    )


def assess_identity(
    left: dict,
    right: dict,
    similarity: PhenotypeSimilarity,
    left_phenotypes: frozenset[str],
    right_phenotypes: frozenset[str],
) -> DiseaseIdentityRelationship:
    """Full identity assessment for one pair."""
    signals = compute_signals(
        left, right, similarity, left_phenotypes, right_phenotypes
    )
    relation, rationale = classify_identity(signals)
    left_id, right_id = sorted((left["disease_id"], right["disease_id"]))
    # Anything other than a clear distinct-disease verdict changes how the pair
    # should be counted, so it goes to a human rather than being applied silently.
    review = (
        ReviewStatus.NOT_REVIEWED
        if relation is IdentityRelation.DISTINCT_DISEASE
        else ReviewStatus.AWAITING_EXPERT_SIGNOFF
    )
    return DiseaseIdentityRelationship(
        identity_id=str(uuid5(NAMESPACE_URL, f"identity|{left_id}|{right_id}")),
        disease_a=left_id,
        disease_b=right_id,
        relation=relation,
        shared_gene_ids=signals.shared_genes,
        rationale=rationale,
        review_status=review,
    )
