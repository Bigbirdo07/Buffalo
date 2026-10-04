"""Find candidate mechanistic neighbours for a disease.

This answers "who shares our disease characteristics, biologically rather than
nominally" -- but only as a *retrieval* step. A candidate is a disease worth
comparing, never a disease we claim is related. The comparison and the evidence
refinement decide that, and they run afterwards.

Three measured facts shaped the design.

**Features differ enormously in how much they discriminate.** Measured over the
corpus, "neuron" appears in 548 diseases, "inflammatory response" in 397,
"apoptotic process" in 236, while the median feature appears in 1-2. Treating
every shared feature alike would fuse most of the corpus into one cluster, so
every feature is weighted by information content from corpus frequency, exactly
as phenotypes are. A feature shared by 548 diseases contributes almost nothing;
one shared by three contributes a lot.

**Two feature classes cannot generate candidates and are excluded.** The corpus
holds 6 distinct model organisms and 12 therapeutic modalities. "Both diseases
have a mouse model" is true of 1,036 diseases and is a description, not a link.
They remain in the fingerprint as context for a comparison already made.

**Pathway overlap is not available.** DisMech annotates pathways for 4 diseases
(0.1%), so the brief's pathway method cannot run from this source. GO biological
process (96.7% coverage) stands in, and is reported under its own name.

Methods stay separate all the way through. There is no blended score, because a
pair matching on genes is a different biological claim from a pair matching on
phenotype, and collapsing them would hide which one fired.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum

from atlas.domain.fingerprint import FeatureClass

# Slots that generate candidates, grouped into the method that reports them.
# cellular == GO biological process + cellular component: the stand-in for the
# pathway layer DisMech does not carry.
METHOD_SLOTS: dict[str, tuple[FeatureClass, ...]] = {
    "SHARED_GENE_OR_PROTEIN": (FeatureClass.GENETIC,),
    "SHARED_CELLULAR_PROCESS": (FeatureClass.CELLULAR,),
    "SHARED_MOLECULAR_FUNCTION": (FeatureClass.MOLECULAR,),
    "SHARED_CELL_OR_TISSUE": (FeatureClass.CELL_TISSUE,),
    "SHARED_PHENOTYPE": (FeatureClass.PHENOTYPE,),
}
# Excluded from retrieval, kept for context. See the module docstring.
NON_DISCRIMINATING = (FeatureClass.MODEL_ORGANISM, FeatureClass.THERAPEUTIC)

# A feature in more than this fraction of the corpus is too common to retrieve
# on: it would return hundreds of diseases that share nothing specific. It is
# still reported when a pair matches for other reasons.
MAX_RETRIEVAL_FREQUENCY = 0.05


class CandidateMethod(StrEnum):
    SHARED_GENE_OR_PROTEIN = "SHARED_GENE_OR_PROTEIN"
    SHARED_CELLULAR_PROCESS = "SHARED_CELLULAR_PROCESS"
    SHARED_MOLECULAR_FUNCTION = "SHARED_MOLECULAR_FUNCTION"
    SHARED_CELL_OR_TISSUE = "SHARED_CELL_OR_TISSUE"
    SHARED_PHENOTYPE = "SHARED_PHENOTYPE"


@dataclass(frozen=True)
class SharedFeature:
    feature_id: str
    label: str
    feature_class: str
    # Diseases in the corpus carrying this feature. Low is informative.
    corpus_frequency: int
    information_content: float
    # Evidence backing this feature in each disease, so a match on a
    # well-evidenced feature is distinguishable from one asserted in passing.
    evidence_left: int
    evidence_right: int
    modifiers_left: tuple[str, ...] = ()
    modifiers_right: tuple[str, ...] = ()

    @property
    def directions_conflict(self) -> bool:
        """True when the two diseases perturb this feature oppositely.

        Not a verdict: upstream modifiers are sparse and a conflict may be
        correct biology. It is a question the comparison must answer.
        """
        opposed = {("INCREASED", "DECREASED"), ("DECREASED", "INCREASED")}
        return any(
            (left, right) in opposed
            for left in self.modifiers_left
            for right in self.modifiers_right
        )


@dataclass
class Candidate:
    """One disease worth comparing, with why it was retrieved."""

    disease_id: str
    disease_name: str
    source_file: str
    # method -> the features that fired it. Never collapsed into one number.
    methods: dict[str, list[SharedFeature]] = field(default_factory=dict)

    @property
    def methods_fired(self) -> tuple[str, ...]:
        return tuple(sorted(self.methods))

    def method_score(self, method: str) -> float:
        """Summed information content of the features firing one method."""
        return round(
            sum(item.information_content for item in self.methods.get(method, [])), 3
        )

    @property
    def scores(self) -> dict[str, float]:
        return {method: self.method_score(method) for method in sorted(self.methods)}

    @property
    def total_information(self) -> float:
        """Ranking aid only. Never presented as a measure of relatedness."""
        return round(sum(self.scores.values()), 3)

    @property
    def conflicting_features(self) -> tuple[SharedFeature, ...]:
        return tuple(
            item
            for features in self.methods.values()
            for item in features
            if item.directions_conflict
        )

    def top_features(self, limit: int = 8) -> tuple[SharedFeature, ...]:
        everything = [item for features in self.methods.values() for item in features]
        everything.sort(key=lambda item: (-item.information_content, item.feature_id))
        return tuple(everything[:limit])


class FeatureIndex:
    """Inverted index feature -> diseases, with corpus-derived weights.

    Retrieval without this is intractable: scoring all 5.4M disease pairs takes
    about an hour, and nearly every pair shares nothing. The index turns that
    into a lookup over the few informative features a disease actually has.
    """

    def __init__(self, fingerprints: list[dict]) -> None:
        self.fingerprints = fingerprints
        self.by_id: dict[str, dict] = {item["disease_id"]: item for item in fingerprints}
        self.disease_count = max(len(fingerprints), 1)
        postings: defaultdict[str, set[str]] = defaultdict(set)
        labels: dict[str, str] = {}
        classes: dict[str, str] = {}
        excluded = {item.value for item in NON_DISCRIMINATING}
        for record in fingerprints:
            for feature in record["features"]:
                if feature["feature_class"] in excluded:
                    continue
                postings[feature["feature_id"]].add(record["disease_id"])
                labels.setdefault(feature["feature_id"], feature["label"])
                classes.setdefault(feature["feature_id"], feature["feature_class"])
        self.postings = {key: frozenset(value) for key, value in postings.items()}
        self.labels = labels
        self.classes = classes
        self.information_content = {
            key: -math.log(len(value) / self.disease_count)
            for key, value in self.postings.items()
        }
        self.retrieval_ceiling = int(self.disease_count * MAX_RETRIEVAL_FREQUENCY)

    def frequency(self, feature_id: str) -> int:
        return len(self.postings.get(feature_id, frozenset()))

    def ic(self, feature_id: str) -> float:
        return self.information_content.get(feature_id, 0.0)

    def is_retrievable(self, feature_id: str) -> bool:
        count = self.frequency(feature_id)
        return 1 < count <= self.retrieval_ceiling

    def method_for(self, feature_class: str) -> str | None:
        for method, classes in METHOD_SLOTS.items():
            if feature_class in {item.value for item in classes}:
                return method
        return None


def generate_candidates(
    index: FeatureIndex,
    disease_id: str,
    *,
    limit: int = 25,
    min_methods: int = 1,
) -> list[Candidate]:
    """Retrieve diseases sharing informative features with the query disease.

    `min_methods` raises the bar to pairs matching on several independent axes,
    which is a far stronger starting point than one shared feature.
    """
    query = index.by_id.get(disease_id)
    if query is None:
        return []

    query_features = {item["feature_id"]: item for item in query["features"]}
    gathered: dict[str, Candidate] = {}

    for feature_id, feature in query_features.items():
        if not index.is_retrievable(feature_id):
            continue
        method = index.method_for(feature["feature_class"])
        if method is None:
            continue
        for other_id in index.postings[feature_id]:
            if other_id == disease_id:
                continue
            other = index.by_id[other_id]
            candidate = gathered.get(other_id)
            if candidate is None:
                candidate = Candidate(
                    disease_id=other_id,
                    disease_name=other["disease_name"],
                    source_file=other["source_file"],
                )
                gathered[other_id] = candidate
            match = next(
                item for item in other["features"] if item["feature_id"] == feature_id
            )
            candidate.methods.setdefault(method, []).append(
                SharedFeature(
                    feature_id=feature_id,
                    label=index.labels.get(feature_id, feature_id),
                    feature_class=feature["feature_class"],
                    corpus_frequency=index.frequency(feature_id),
                    information_content=round(index.ic(feature_id), 3),
                    evidence_left=int(feature.get("evidence_count", 0)),
                    evidence_right=int(match.get("evidence_count", 0)),
                    modifiers_left=tuple(feature.get("modifiers") or ()),
                    modifiers_right=tuple(match.get("modifiers") or ()),
                )
            )

    results = [
        candidate
        for candidate in gathered.values()
        if len(candidate.methods) >= min_methods
    ]
    for candidate in results:
        for features in candidate.methods.values():
            features.sort(key=lambda item: (-item.information_content, item.feature_id))
    # Rank by independent axes first, then total information. Sorting by one
    # blended number would hide that a four-axis match differs in kind from a
    # single strong gene match.
    results.sort(
        key=lambda item: (-len(item.methods), -item.total_information, item.disease_id)
    )
    return results[:limit]


def coverage_note(index: FeatureIndex) -> dict[str, object]:
    """What retrieval can and cannot see, travelling with any result set."""
    retrievable = sum(1 for key in index.postings if index.is_retrievable(key))
    singletons = sum(1 for value in index.postings.values() if len(value) == 1)
    return {
        "diseases_indexed": index.disease_count,
        "features_indexed": len(index.postings),
        "features_usable_for_retrieval": retrievable,
        "features_in_one_disease_only": singletons,
        "features_too_common_to_retrieve_on": sum(
            1 for key in index.postings if index.frequency(key) > index.retrieval_ceiling
        ),
        "retrieval_ceiling_diseases": index.retrieval_ceiling,
        "excluded_classes": [item.value for item in NON_DISCRIMINATING],
        "pathway_layer": (
            "DisMech annotates pathways for 4 of 3,289 diseases; GO biological "
            "process is used as the process layer and reported as such."
        ),
        "limitation": (
            "Retrieval finds diseases sharing annotated features. A real "
            "mechanistic relationship that upstream has not annotated in both "
            "diseases is invisible here, so an empty result means no shared "
            "annotation, not no relationship."
        ),
    }
