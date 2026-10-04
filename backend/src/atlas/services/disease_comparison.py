"""Interpretable pairwise comparison of two candidate neighbour diseases.

Retrieval says two diseases share annotated features. This module says *what*
they share, *where they differ*, and *what would have to be true* for the shared
biology to be real. It produces no verdict on whether the relationship holds:
that is the refinement engine's job, and keeping the two apart is what stops a
similarity score from being mistaken for evidence.

The design follows the project's existing discipline. Overlap is reported as a
category with a stated rule, never as a number pretending to be a measurement.
Every axis can come back NOT_ASSESSABLE, which is a real and common answer when
upstream has not annotated the dimension in both diseases.

The hardest rule here is variant compatibility, which the brief marks mandatory
and which exists because the same gene can cause opposite diseases. Two
disorders of one gene are not mechanistically equivalent when one is a
loss-of-function and the other a gain-of-function, and a system that called them
neighbours because the gene symbol matched would be actively misleading.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.services.candidate_generation import Candidate, FeatureIndex, SharedFeature
from atlas.services.hpo_similarity import (
    PhenotypeComparison,
    PhenotypeSimilarity,
    compare_phenotypes,
)

# Summed information content of an axis's shared features. The bands are a
# reporting convention, documented so a reader can disagree with them; they
# describe how unusual the overlap is, not how real the relationship is.
STRONG_OVERLAP_IC = 10.0
MODERATE_OVERLAP_IC = 5.0

# Variant effect vocabulary, grouped by what it implies for mechanism.
LOSS_TERMS = frozenset(
    {
        "loss_of_function",
        "loss of function",
        "haploinsufficiency",
        "nonsense",
        "frameshift",
        "truncating",
        "deletion",
    }
)
GAIN_TERMS = frozenset({"gain_of_function", "gain of function", "duplication"})
DOMINANT_NEGATIVE_TERMS = frozenset({"dominant_negative", "dominant negative"})


class OverlapStrength(StrEnum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    NONE = "NONE"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"


class CompatibilityStatus(StrEnum):
    """Whether the two diseases' variant effects can describe one mechanism."""

    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNDETERMINED = "UNDETERMINED"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"


@dataclass(frozen=True)
class ComparisonAxis:
    name: str
    strength: OverlapStrength
    shared: tuple[SharedFeature, ...]
    information: float
    rule: str

    @property
    def shared_labels(self) -> tuple[str, ...]:
        return tuple(item.label for item in self.shared)


@dataclass(frozen=True)
class VariantCompatibility:
    """The check that stops a shared gene symbol from implying shared mechanism."""

    status: CompatibilityStatus
    left_effects: tuple[str, ...]
    right_effects: tuple[str, ...]
    shared_genes: tuple[str, ...]
    reason: str

    @property
    def is_blocking(self) -> bool:
        return self.status is CompatibilityStatus.INCOMPATIBLE


@dataclass(frozen=True)
class EvidenceAsymmetry:
    """One disease being far better evidenced changes what a comparison means."""

    left_evidence: int
    right_evidence: int
    ratio: float
    note: str


@dataclass(frozen=True)
class DiseaseComparison:
    left_id: str
    left_name: str
    right_id: str
    right_name: str
    retrieval_methods: tuple[str, ...]
    axes: tuple[ComparisonAxis, ...]
    phenotypes: PhenotypeComparison
    variant_compatibility: VariantCompatibility
    direction_conflicts: tuple[SharedFeature, ...]
    evidence_asymmetry: EvidenceAsymmetry
    caveats: tuple[str, ...]

    def axis(self, name: str) -> ComparisonAxis | None:
        return next((item for item in self.axes if item.name == name), None)

    @property
    def strong_axes(self) -> tuple[str, ...]:
        return tuple(
            item.name for item in self.axes if item.strength is OverlapStrength.STRONG
        )

    @property
    def has_molecular_anchor(self) -> bool:
        """Whether anything below the phenotype level genuinely ties these diseases.

        A pair matching only on phenotype and anatomy may share a clinical
        picture with no common mechanism at all, which is the single most
        important distinction this comparison draws.

        The rule was tightened after seeing SCAR16 against Rabies, and the change
        is disclosed because it was made in response to a case. Originally any
        non-NONE match on gene, molecular function or cellular process counted,
        which called Rabies anchored on a single moderate "mitophagy" term. A
        shared process annotation between an acute viral encephalitis and a
        genetic proteostasis disorder is a coincidence of annotation, not a
        molecular tie.

        A gene or molecular-function match anchors at any strength, because those
        are specific claims about the same protein or activity. A process match
        anchors only when STRONG, because process terms are broad and shared
        widely. Under this rule SCA48 anchors (STUB1 plus Hsp70 binding), while
        Lafora disease and Rabies do not.
        """
        return has_molecular_anchor(self.axes)


def has_molecular_anchor(axes: tuple[ComparisonAxis, ...]) -> bool:
    """Shared by the comparison property and the caveat text, so they cannot drift.

    Keeping these in one place is not tidiness: an earlier version computed the
    caveat from a looser rule than the property, so Rabies was reported as
    molecularly anchored while the caveat explaining the absence of an anchor was
    suppressed. A test caught it.
    """
    for item in axes:
        if item.strength is OverlapStrength.NONE:
            continue
        if item.name in {"SHARED_GENE_OR_PROTEIN", "SHARED_MOLECULAR_FUNCTION"}:
            return True
        if (
            item.name == "SHARED_CELLULAR_PROCESS"
            and item.strength is OverlapStrength.STRONG
        ):
            return True
    return False


def _strength(information: float, shared: tuple[SharedFeature, ...]) -> OverlapStrength:
    if not shared:
        return OverlapStrength.NONE
    if information >= STRONG_OVERLAP_IC:
        return OverlapStrength.STRONG
    if information >= MODERATE_OVERLAP_IC:
        return OverlapStrength.MODERATE
    return OverlapStrength.WEAK


def _classify_effects(effects: frozenset[str]) -> set[str]:
    classes: set[str] = set()
    if effects & LOSS_TERMS:
        classes.add("LOSS")
    if effects & GAIN_TERMS:
        classes.add("GAIN")
    if effects & DOMINANT_NEGATIVE_TERMS:
        classes.add("DOMINANT_NEGATIVE")
    return classes


def assess_variant_compatibility(
    left: dict, right: dict, shared_genes: tuple[str, ...]
) -> VariantCompatibility:
    """Decide whether two diseases' variant effects can describe one mechanism.

    Deliberately conservative. Upstream variant-effect annotation is sparse free
    text, so the common answer is NOT_ASSESSABLE, and saying so is better than
    inferring a compatibility the source does not state.
    """
    left_effects = frozenset(left.get("variant_effects") or ())
    right_effects = frozenset(right.get("variant_effects") or ())

    if not shared_genes:
        return VariantCompatibility(
            status=CompatibilityStatus.NOT_ASSESSABLE,
            left_effects=tuple(sorted(left_effects)),
            right_effects=tuple(sorted(right_effects)),
            shared_genes=(),
            reason=(
                "No shared gene, so variant effects describe different proteins and "
                "are not comparable. Any shared mechanism must be argued at the "
                "process level instead."
            ),
        )
    if not left_effects or not right_effects:
        missing = left["disease_name"] if not left_effects else right["disease_name"]
        return VariantCompatibility(
            status=CompatibilityStatus.NOT_ASSESSABLE,
            left_effects=tuple(sorted(left_effects)),
            right_effects=tuple(sorted(right_effects)),
            shared_genes=shared_genes,
            reason=(
                f"No variant effect recorded upstream for {missing}, so "
                "compatibility cannot be assessed. The shared gene alone does not "
                "establish a shared mechanism."
            ),
        )

    left_classes = _classify_effects(left_effects)
    right_classes = _classify_effects(right_effects)
    opposed = ("LOSS" in left_classes and "GAIN" in right_classes) or (
        "GAIN" in left_classes and "LOSS" in right_classes
    )
    if opposed:
        return VariantCompatibility(
            status=CompatibilityStatus.INCOMPATIBLE,
            left_effects=tuple(sorted(left_effects)),
            right_effects=tuple(sorted(right_effects)),
            shared_genes=shared_genes,
            reason=(
                "Opposite functional directions on a shared gene: one disease is "
                "annotated loss-of-function and the other gain-of-function. The "
                "same gene can cause opposite diseases, so these are not "
                "mechanistically equivalent despite the gene match."
            ),
        )
    if not left_classes or not right_classes:
        return VariantCompatibility(
            status=CompatibilityStatus.UNDETERMINED,
            left_effects=tuple(sorted(left_effects)),
            right_effects=tuple(sorted(right_effects)),
            shared_genes=shared_genes,
            reason=(
                "Variant effects are recorded but do not resolve to a functional "
                "direction, so compatibility is undetermined rather than assumed."
            ),
        )
    if left_classes == right_classes:
        return VariantCompatibility(
            status=CompatibilityStatus.COMPATIBLE,
            left_effects=tuple(sorted(left_effects)),
            right_effects=tuple(sorted(right_effects)),
            shared_genes=shared_genes,
            reason=(
                f"Both diseases are annotated {'/'.join(sorted(left_classes))} on a "
                "shared gene. Compatible in direction; this does not by itself show "
                "the downstream consequences are equivalent."
            ),
        )
    return VariantCompatibility(
        status=CompatibilityStatus.UNDETERMINED,
        left_effects=tuple(sorted(left_effects)),
        right_effects=tuple(sorted(right_effects)),
        shared_genes=shared_genes,
        reason=(
            f"Differing effect classes ({'/'.join(sorted(left_classes))} versus "
            f"{'/'.join(sorted(right_classes))}) on a shared gene. Whether these "
            "converge on one mechanism needs comparative functional data."
        ),
    )


def compare_diseases(
    index: FeatureIndex,
    candidate: Candidate,
    query_id: str,
    similarity: PhenotypeSimilarity,
    left_phenotypes: frozenset[str],
    right_phenotypes: frozenset[str],
) -> DiseaseComparison:
    """Build the interpretable comparison for one retrieved candidate."""
    left = index.by_id[query_id]
    right = index.by_id[candidate.disease_id]

    axes: list[ComparisonAxis] = []
    for method in sorted(candidate.methods):
        shared = tuple(candidate.methods[method])
        information = round(sum(item.information_content for item in shared), 3)
        axes.append(
            ComparisonAxis(
                name=method,
                strength=_strength(information, shared),
                shared=shared,
                information=information,
                rule=(
                    f"summed information content {information} "
                    f"(STRONG >= {STRONG_OVERLAP_IC}, MODERATE >= {MODERATE_OVERLAP_IC})"
                ),
            )
        )

    shared_genes = tuple(
        item.label
        for item in candidate.methods.get("SHARED_GENE_OR_PROTEIN", [])
        if item.feature_id.startswith("HGNC:")
    )
    compatibility = assess_variant_compatibility(left, right, shared_genes)

    left_evidence = int(left["coverage"]["evidence_items"])
    right_evidence = int(right["coverage"]["evidence_items"])
    low, high = sorted((left_evidence, right_evidence))
    ratio = round(high / low, 2) if low else float("inf")
    asymmetry = EvidenceAsymmetry(
        left_evidence=left_evidence,
        right_evidence=right_evidence,
        ratio=ratio,
        note=(
            "Comparable evidence depth."
            if ratio <= 3
            else (
                "One disease is substantially better evidenced than the other, so "
                "an apparent difference may reflect curation depth rather than "
                "biology."
            )
        ),
    )

    phenotypes = compare_phenotypes(similarity, left_phenotypes, right_phenotypes)
    conflicts = candidate.conflicting_features

    caveats: list[str] = []
    if not has_molecular_anchor(tuple(axes)):
        caveats.append(
            "No molecular or process-level overlap: these diseases are linked only "
            "by phenotype and anatomy, which can arise without any shared mechanism."
        )
    if conflicts:
        caveats.append(
            "Shared features are annotated in opposite directions in the two "
            "diseases, which argues against functional equivalence."
        )
    if compatibility.is_blocking:
        caveats.append(compatibility.reason)
    if ratio > 3:
        caveats.append(asymmetry.note)
    for missing in right["coverage"]["missing_dimensions"]:
        caveats.append(
            f"{right['disease_name']} has no {missing} annotation, so that axis is "
            "unassessed rather than absent."
        )

    return DiseaseComparison(
        left_id=query_id,
        left_name=left["disease_name"],
        right_id=candidate.disease_id,
        right_name=candidate.disease_name,
        retrieval_methods=candidate.methods_fired,
        axes=tuple(axes),
        phenotypes=phenotypes,
        variant_compatibility=compatibility,
        direction_conflicts=conflicts,
        evidence_asymmetry=asymmetry,
        caveats=tuple(dict.fromkeys(caveats)),
    )
