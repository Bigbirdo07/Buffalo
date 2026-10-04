"""Ontology-aware phenotype comparison over HPO.

Why not embeddings or string matching: "Ataxia" and "Cerebellar ataxia" are not
the same term, and "Abnormality of the nervous system" is shared by most
neurological disorders while telling you almost nothing. Both facts need the
ontology's structure. Text similarity gets the first wrong and the second
catastrophically wrong, because the least informative terms are also the most
frequently written.

The method is Resnik's: the similarity of two terms is the information content
of their most informative common ancestor (MICA). Information content comes from
*this corpus* — a term annotating few diseases is informative, one annotating
many is not — so it reflects the actual annotation distribution rather than an
imported table that may not match.

Disease-level comparison uses symmetric best-match average. One number is kept
for candidate ranking only; what gets shown is the partition, because "these two
diseases share cerebellar atrophy" is a biological statement a reader can check,
while "similarity 0.62" is not:

    shared informative   both diseases, high-IC term -> the interesting overlap
    shared generic       both diseases, low-IC term  -> explains little
    distinctive          one disease only, high IC   -> what separates them
    unmatched            one disease only, low IC

A high score is a reason to look, never a finding. Nothing here decides whether
two diseases share a mechanism; that is the refinement engine's job.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

# A term annotating <=5% of diseases is treated as informative: IC >= ~3.0 nats.
#
# This threshold was changed after seeing data, which is disclosed because a
# threshold tuned on an example and then reported as if chosen a priori is not
# honest. The first value was 1% (IC >= 4.61). Calibrating on SCAR16 vs SCAR20 --
# two recessive cerebellar ataxias whose overlap is not in dispute -- that value
# classified "Cerebellar atrophy" (IC 3.16, 140 diseases) as generic and left the
# shared-informative set empty, which is wrong: for two ataxias that term is the
# overlap. It also emptied the ancestor-match list, since "Pontocerebellar
# atrophy" relates to "Cerebellar atrophy" through an ancestor below 4.61.
#
# At 5% the generic set still correctly holds the terms that would otherwise
# dominate any similarity measure -- Seizure (697 diseases, IC 1.40), Global
# developmental delay (624), Intellectual disability (550), Hypotonia (433).
# Measured over 17,111 shared-term co-occurrences the median IC is 2.21, so the
# threshold sits above the typical shared term by design.
#
# It is a reporting choice, not a mathematical one: it decides which overlaps are
# shown as interesting, never whether a relationship is real. A test pins both
# the Seizure-is-generic and the Cerebellar-atrophy-is-informative cases.
INFORMATIVE_IC_PERCENTILE = 0.05
_ID = re.compile(r"^HP:\d{7}$")


@dataclass(frozen=True)
class HpoTerm:
    term_id: str
    name: str
    parents: tuple[str, ...]
    obsolete: bool = False
    replaced_by: str | None = None


class HpoOntology:
    """Parsed HPO with transitive ancestor closure."""

    def __init__(self, terms: dict[str, HpoTerm], alt_ids: dict[str, str]) -> None:
        self.terms = terms
        self.alt_ids = alt_ids

    @classmethod
    def from_obo(cls, path: Path) -> HpoOntology:
        terms: dict[str, HpoTerm] = {}
        alt_ids: dict[str, str] = {}
        term_id = name = replaced_by = None
        parents: list[str] = []
        local_alts: list[str] = []
        obsolete = False
        in_term = False

        def flush() -> None:
            if in_term and term_id and _ID.match(term_id):
                terms[term_id] = HpoTerm(
                    term_id=term_id,
                    name=name or term_id,
                    parents=tuple(parents),
                    obsolete=obsolete,
                    replaced_by=replaced_by,
                )
                for alt in local_alts:
                    alt_ids[alt] = term_id

        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line in {"[Term]", "[Typedef]"}:
                flush()
                in_term = line == "[Term]"
                term_id = name = replaced_by = None
                parents, local_alts, obsolete = [], [], False
                continue
            if not in_term or ": " not in line:
                continue
            key, _, value = line.partition(": ")
            if key == "id":
                term_id = value.strip()
            elif key == "name":
                name = value.strip()
            elif key == "alt_id":
                local_alts.append(value.strip())
            elif key == "is_a":
                parents.append(value.split("!")[0].strip())
            elif key == "is_obsolete":
                obsolete = value.strip() == "true"
            elif key == "replaced_by":
                replaced_by = value.strip()
        flush()
        return cls(terms, alt_ids)

    def canonical(self, term_id: str) -> str | None:
        """Resolve alt ids and obsolete terms to a usable current term."""
        resolved = self.alt_ids.get(term_id, term_id)
        term = self.terms.get(resolved)
        if term is None:
            return None
        if term.obsolete:
            return term.replaced_by if term.replaced_by in self.terms else None
        return resolved

    @cached_property
    def _ancestors(self) -> dict[str, frozenset[str]]:
        cache: dict[str, frozenset[str]] = {}

        def walk(node: str, seen: frozenset[str]) -> frozenset[str]:
            if node in cache:
                return cache[node]
            if node in seen:  # defensive: the ontology is a DAG, not a tree
                return frozenset([node])
            term = self.terms.get(node)
            if term is None:
                return frozenset()
            result = {node}
            for parent in term.parents:
                result |= walk(parent, seen | {node})
            closure = frozenset(result)
            cache[node] = closure
            return closure

        for identifier in self.terms:
            walk(identifier, frozenset())
        return cache

    def ancestors(self, term_id: str) -> frozenset[str]:
        """The term itself plus every is_a ancestor."""
        return self._ancestors.get(term_id, frozenset())


class PhenotypeSimilarity:
    """Resnik similarity with information content derived from the corpus."""

    def __init__(self, ontology: HpoOntology, annotation_sets: list[frozenset[str]]) -> None:
        self.ontology = ontology
        self.disease_count = max(len(annotation_sets), 1)
        counts: Counter[str] = Counter()
        for annotation_set in annotation_sets:
            # Propagate to ancestors: annotating a child implies the parent.
            closure: set[str] = set()
            for term in annotation_set:
                closure |= ontology.ancestors(term)
            counts.update(closure)
        self.term_counts = counts
        self.information_content = {
            term: -math.log(count / self.disease_count)
            for term, count in counts.items()
            if count > 0
        }
        self.informative_threshold = -math.log(INFORMATIVE_IC_PERCENTILE)

    def ic(self, term_id: str) -> float:
        return self.information_content.get(term_id, 0.0)

    def is_informative(self, term_id: str) -> bool:
        return self.ic(term_id) >= self.informative_threshold

    def mica(self, left: str, right: str) -> tuple[str | None, float]:
        """Most informative common ancestor and its information content."""
        common = self.ontology.ancestors(left) & self.ontology.ancestors(right)
        if not common:
            return None, 0.0
        best = max(common, key=lambda term: (self.ic(term), term))
        return best, self.ic(best)

    def best_match_average(
        self, left: frozenset[str], right: frozenset[str]
    ) -> float:
        """Symmetric best-match average, the standard disease-level aggregate."""
        if not left or not right:
            return 0.0

        def directional(source: frozenset[str], target: frozenset[str]) -> float:
            return sum(
                max(self.mica(term, other)[1] for other in target) for term in source
            ) / len(source)

        return (directional(left, right) + directional(right, left)) / 2


@dataclass(frozen=True)
class PhenotypeComparison:
    """The explainable output: a partition, not only a number."""

    shared_informative: tuple[tuple[str, str, float], ...]
    shared_generic: tuple[tuple[str, str, float], ...]
    distinctive_left: tuple[tuple[str, str], ...]
    distinctive_right: tuple[tuple[str, str], ...]
    unmatched_left: int
    unmatched_right: int
    best_match_average: float
    # Near-matches: different terms sharing an informative ancestor. These are
    # often the biologically interesting overlap, since curators rarely choose
    # the identical term for two different disorders.
    related_via_ancestor: tuple[tuple[str, str, str, float], ...]

    @property
    def has_informative_overlap(self) -> bool:
        return bool(self.shared_informative or self.related_via_ancestor)


def compare_phenotypes(
    similarity: PhenotypeSimilarity,
    left: frozenset[str],
    right: frozenset[str],
    *,
    max_related: int = 10,
) -> PhenotypeComparison:
    """Partition two phenotype sets into the four interpretable groups."""
    ontology = similarity.ontology
    shared = left & right
    shared_informative = []
    shared_generic = []
    for term in sorted(shared, key=lambda item: -similarity.ic(item)):
        label = ontology.terms[term].name if term in ontology.terms else term
        row = (term, label, round(similarity.ic(term), 3))
        if similarity.is_informative(term):
            shared_informative.append(row)
        else:
            shared_generic.append(row)

    related: list[tuple[str, str, str, float]] = []
    for term in left - right:
        best_term: str | None = None
        best_ancestor: str | None = None
        best_ic = 0.0
        for other in right - left:
            ancestor, score = similarity.mica(term, other)
            if ancestor and score > best_ic:
                best_term, best_ancestor, best_ic = other, ancestor, score
        if best_term and best_ancestor and best_ic >= similarity.informative_threshold:
            related.append((term, best_term, best_ancestor, round(best_ic, 3)))
    related.sort(key=lambda row: -row[3])
    related = related[:max_related]
    paired = {row[0] for row in related} | {row[1] for row in related}

    def distinctive(side: frozenset[str], other: frozenset[str]) -> list[tuple[str, str]]:
        return [
            (term, ontology.terms[term].name if term in ontology.terms else term)
            for term in sorted(side - other, key=lambda item: -similarity.ic(item))
            if similarity.is_informative(term) and term not in paired
        ]

    distinct_left = distinctive(left, right)
    distinct_right = distinctive(right, left)
    return PhenotypeComparison(
        shared_informative=tuple(shared_informative),
        shared_generic=tuple(shared_generic),
        distinctive_left=tuple(distinct_left[:15]),
        distinctive_right=tuple(distinct_right[:15]),
        unmatched_left=len(left - right) - len(distinct_left),
        unmatched_right=len(right - left) - len(distinct_right),
        best_match_average=round(similarity.best_match_average(left, right), 4),
        related_via_ancestor=tuple(related),
    )


def load_annotation_sets(
    ontology: HpoOntology, phenotype_lists: list[list[str]]
) -> list[frozenset[str]]:
    """Canonicalize raw HPO ids, dropping those the ontology cannot resolve."""
    resolved: list[frozenset[str]] = []
    for identifiers in phenotype_lists:
        canonical = {
            canon
            for canon in (ontology.canonical(item.upper()) for item in identifiers)
            if canon is not None
        }
        resolved.append(frozenset(canonical))
    return resolved


def unresolved_terms(ontology: HpoOntology, identifiers: list[str]) -> list[str]:
    """Ids the ontology cannot resolve, reported rather than silently dropped."""
    return sorted(
        {item for item in identifiers if ontology.canonical(item.upper()) is None}
    )


def ancestor_closure(ontology: HpoOntology, terms: frozenset[str]) -> frozenset[str]:
    closure: set[str] = set()
    for term in terms:
        closure |= ontology.ancestors(term)
    return frozenset(closure)
