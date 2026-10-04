"""The cross-disease decision pipeline: candidate pair in, classified relationship out.

Every pair runs the same ordered stages, and no stage is skipped because a
candidate looks obvious. The order matters: identity is settled before any
mechanism claim, because two labels for one allelic spectrum are a data-model
question rather than a discovery, and a system that skips that check reports
"we connected two diseases" when it has found two names for one.

The pipeline takes evidence as an explicit input and cannot reach it any other
way. It has no network access, no file access and no knowledge of any review
verdict, so a blind run is blind by construction rather than by discipline. The
sealed verdicts used to evaluate it live in a file this module never reads.

Classification is a rule cascade with every rule stated. There is no score. Each
stage records what it found and what it could not assess, so a result can be
disputed at the specific step rather than in aggregate.

Nothing here names a disease, gene, pathway or cell type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from atlas.domain.cross_disease import (
    CompatibilityVerdict,
    IdentityRelation,
    ReasonType,
    RelationshipClass,
    RetrievalReason,
    RetrievalValidity,
    ReviewStatus,
    ValidatedRelationship,
)
from atlas.services.candidate_generation import Candidate
from atlas.services.disease_comparison import DiseaseComparison, OverlapStrength

PIPELINE_VERSION = "cross-disease-pipeline-v1"

# Independent primary findings required before asserting a shared mechanism.
#
# Symmetry with an existing rule: this system already refuses to call a claim
# contradicted on one publication. Asserting a mechanism is at least as strong a
# statement, so it is held to the same bar. Measured effect on the first blind
# run: one pair rested on a single paper and was reported as a shared mechanism;
# under corroboration it becomes INSUFFICIENT_EVIDENCE, which is what a single
# report actually supports.
MINIMUM_CORROBORATION = 2


@dataclass(frozen=True)
class MechanisticEvidence:
    """One retrieved, assessed piece of evidence bearing on a proposed link.

    Supplied by the refinement engine. The pipeline never fetches anything: it
    classifies what it is given, so the same inputs always yield the same answer.
    """

    evidence_id: str
    # SUPPORTS / REFUTES / QUALIFIES, as the existing critic assigns.
    polarity: str
    # Does this evidence speak to a direct molecular link between the two
    # diseases' proteins or processes, or only to one disease in isolation?
    establishes_direct_link: bool
    # Is the cited statement the paper's own result, or attributed background?
    is_primary_finding: bool
    # Free-text description of what the evidence shows, for the rationale.
    statement: str = ""
    caveats: tuple[str, ...] = ()


@dataclass(frozen=True)
class AlternativeExplanation:
    """A way the similarity could arise without a shared mechanism."""

    code: str
    description: str
    # True when the pair's own features are consistent with this alternative.
    applies: bool


@dataclass
class StageRecord:
    stage: str
    finding: str
    assessable: bool = True


@dataclass
class DecisionTrace:
    """The ordered record of how a classification was reached."""

    pair_id: str
    disease_a: str
    disease_b: str
    stages: list[StageRecord] = field(default_factory=list)
    identity_relation: IdentityRelation | None = None
    retrieval_reasons: tuple[RetrievalReason, ...] = ()
    retrieval_validity: RetrievalValidity = RetrievalValidity.UNRESOLVED
    variant_compatibility: CompatibilityVerdict = CompatibilityVerdict.UNKNOWN
    molecular_anchor_present: bool = False
    molecular_anchor_description: str = ""
    supporting_evidence_ids: tuple[str, ...] = ()
    contradicting_evidence_ids: tuple[str, ...] = ()
    qualifying_evidence_ids: tuple[str, ...] = ()
    alternative_explanations: tuple[AlternativeExplanation, ...] = ()
    final_relationship_class: RelationshipClass = RelationshipClass.UNKNOWN
    final_rationale: str = ""
    actionable: bool = False
    pipeline_version: str = PIPELINE_VERSION
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def record(self, stage: str, finding: str, *, assessable: bool = True) -> None:
        self.stages.append(StageRecord(stage=stage, finding=finding, assessable=assessable))

    @property
    def stage_names(self) -> tuple[str, ...]:
        return tuple(item.stage for item in self.stages)


# The stages, in required order. Named so a run can be checked for completeness
# rather than trusted to have executed them.
REQUIRED_STAGES: tuple[str, ...] = (
    "DiseaseIdentityCheck",
    "RetrievalReasonInspection",
    "MolecularAnchorInspection",
    "VariantEffectCompatibility",
    "ProcessComparison",
    "CellTypeTissueComparison",
    "PhenotypeComparison",
    "EvidenceRetrieval",
    "EvidenceFitReview",
    "ContradictionSearch",
    "AlternativeExplanationGeneration",
    "MechanisticSynthesis",
)


def generate_alternatives(
    comparison: DiseaseComparison, identity: IdentityRelation
) -> tuple[AlternativeExplanation, ...]:
    """Enumerate ways the similarity could arise without a shared mechanism.

    Each alternative is tested against the pair's own features, so the list says
    which ones actually apply rather than reciting every possibility.
    """
    phenotype_axis = comparison.axis("SHARED_PHENOTYPE")
    process_axis = comparison.axis("SHARED_CELLULAR_PROCESS")
    tissue_axis = comparison.axis("SHARED_CELL_OR_TISSUE")
    gene_axis = comparison.axis("SHARED_GENE_OR_PROTEIN")

    return (
        AlternativeExplanation(
            code="GENERIC_PHENOTYPE_OVERLAP",
            description=(
                "The diseases share symptoms without sharing a cause. Clinical "
                "overlap is common between disorders of the same organ."
            ),
            applies=bool(phenotype_axis and phenotype_axis.shared)
            and not comparison.has_molecular_anchor,
        ),
        AlternativeExplanation(
            code="SHARED_TISSUE_DIFFERENT_BIOLOGY",
            description=(
                "The same cell type or tissue is affected by unrelated processes. "
                "A vulnerable cell population appears in many unrelated disorders."
            ),
            applies=bool(tissue_axis and tissue_axis.shared)
            and not comparison.has_molecular_anchor,
        ),
        AlternativeExplanation(
            code="BROAD_ONTOLOGY_ANNOTATION",
            description=(
                "The shared process term is broad enough to cover mechanistically "
                "distinct branches, so the annotation matches while the biology "
                "does not."
            ),
            applies=bool(
                process_axis
                and process_axis.shared
                and process_axis.strength
                in {OverlapStrength.WEAK, OverlapStrength.MODERATE}
            ),
        ),
        AlternativeExplanation(
            code="SAME_ENTITY_TWO_LABELS",
            description=(
                "The two labels describe one disease or one allelic spectrum, so "
                "the apparent connection is nomenclature rather than biology."
            ),
            applies=identity
            in {
                IdentityRelation.SAME_DISEASE,
                IdentityRelation.ALLELIC_SPECTRUM,
                IdentityRelation.PHENOTYPIC_SUBTYPE,
                IdentityRelation.HISTORICAL_SYNONYM,
            },
        ),
        AlternativeExplanation(
            code="OPPOSITE_DIRECTION",
            description=(
                "The shared feature is perturbed in opposite directions, which "
                "argues against functional equivalence."
            ),
            applies=bool(comparison.direction_conflicts),
        ),
        AlternativeExplanation(
            code="HUB_GENE_EFFECT",
            description=(
                "The shared gene participates in many disorders, so sharing it "
                "describes a research area rather than a specific mechanism."
            ),
            applies=bool(
                gene_axis
                and any(item.corpus_frequency > 33 for item in gene_axis.shared)
            ),
        ),
        AlternativeExplanation(
            code="CURATION_DEPTH_ARTIFACT",
            description=(
                "One disease is far better annotated than the other, so apparent "
                "similarity or difference may reflect curation rather than biology."
            ),
            applies=comparison.evidence_asymmetry.ratio > 3,
        ),
    )


def classify(
    comparison: DiseaseComparison,
    identity: IdentityRelation,
    evidence: tuple[MechanisticEvidence, ...],
) -> tuple[RelationshipClass, str, bool]:
    """Rule cascade from features and evidence to a relationship class.

    Ordered from strongest determinant down. Identity outranks everything,
    because a mechanism shared between two labels for one disease is not a
    cross-disease finding. Evidence outranks annotation: no amount of feature
    overlap reaches a mechanistic class without evidence establishing a direct
    link, which is the rule the whole project turns on.
    """
    # 1. Identity first.
    if identity is IdentityRelation.SAME_DISEASE:
        return (
            RelationshipClass.SAME_DISEASE_ENTITY,
            "Upstream already treats these records as one disease entity.",
            False,
        )
    if identity in {IdentityRelation.ALLELIC_SPECTRUM, IdentityRelation.PHENOTYPIC_SUBTYPE}:
        return (
            RelationshipClass.SAME_ALLELIC_SPECTRUM,
            "Shared causal gene with overlapping presentation: these labels "
            "describe one allelic spectrum, so any shared biology is expected "
            "and this is not an independent cross-disease relationship.",
            False,
        )

    supporting = [item for item in evidence if item.polarity == "SUPPORTS"]
    refuting = [item for item in evidence if item.polarity == "REFUTES"]
    direct = [item for item in supporting if item.establishes_direct_link]
    primary_direct = [item for item in direct if item.is_primary_finding]

    # 2. Refutation outranks support.
    if refuting and not direct:
        return (
            RelationshipClass.CONTRADICTED,
            "Retrieved evidence argues against the proposed link and no evidence "
            "establishes a direct molecular connection.",
            False,
        )

    # 3. Direct evidence of a molecular link is the only route to a mechanistic
    #    class. Annotation overlap never reaches here.
    if len(primary_direct) >= MINIMUM_CORROBORATION:
        return (
            RelationshipClass.SHARED_DOWNSTREAM_MECHANISM,
            f"{len(primary_direct)} independent primary findings establish a "
            "direct molecular link between the two diseases' proteins or "
            "processes, independent of the annotation that retrieved the pair.",
            True,
        )
    if primary_direct:
        return (
            RelationshipClass.INSUFFICIENT_EVIDENCE,
            f"Only {len(primary_direct)} primary finding describes a direct link. "
            "Asserting a shared mechanism requires corroboration, the same "
            "standard this system applies before accepting that a claim is "
            "contradicted. A single report is a lead, not an established link.",
            False,
        )
    if direct:
        return (
            RelationshipClass.INSUFFICIENT_EVIDENCE,
            "Evidence describes a direct link but is attributed background rather "
            "than a primary finding, so the link is reported as unestablished.",
            False,
        )

    # 4. No direct evidence. The class now describes what is actually shared.
    if not comparison.has_molecular_anchor:
        phenotype_axis = comparison.axis("SHARED_PHENOTYPE")
        tissue_axis = comparison.axis("SHARED_CELL_OR_TISSUE")
        if phenotype_axis and phenotype_axis.strength is OverlapStrength.STRONG:
            return (
                RelationshipClass.SHARED_PHENOTYPE_ONLY,
                "Overlap is confined to phenotype and anatomy, with no molecular "
                "or process-level anchor and no evidence of a direct link.",
                False,
            )
        if tissue_axis and tissue_axis.shared:
            return (
                RelationshipClass.SHARED_TISSUE_CONTEXT,
                "The diseases affect comparable tissue without any demonstrated "
                "molecular relationship.",
                False,
            )
        return (
            RelationshipClass.RETRIEVAL_ARTIFACT,
            "Nothing beyond broad annotation connects these diseases, and no "
            "evidence supports a biological relationship.",
            False,
        )

    # 5. A molecular anchor exists but nothing shows the mechanisms are the same.
    if comparison.variant_compatibility.is_blocking:
        return (
            RelationshipClass.SHARED_CELLULAR_PROCESS_NON_EQUIVALENT,
            "A shared molecular feature exists, but variant effects are "
            "incompatible, so the diseases engage the process differently.",
            False,
        )
    if comparison.direction_conflicts:
        return (
            RelationshipClass.SHARED_CELLULAR_PROCESS_NON_EQUIVALENT,
            "The shared feature is perturbed in opposite directions in the two "
            "diseases, which argues against functional equivalence.",
            False,
        )
    return (
        RelationshipClass.SHARED_CELLULAR_PROCESS_NON_EQUIVALENT,
        "The diseases share a molecular or process-level annotation, but no "
        "evidence demonstrates that they disrupt it equivalently. Shared process "
        "is reported; shared mechanism is not claimed.",
        False,
    )


def assess_retrieval_validity(
    comparison: DiseaseComparison,
    final_class: RelationshipClass,
    evidence: tuple[MechanisticEvidence, ...],
) -> RetrievalValidity:
    """Judge whether the reason the pair was retrieved explains the outcome.

    The interesting value is INCORRECT_BUT_CONNECTION_REAL: a genuine
    relationship whose supporting evidence has nothing to do with the feature
    that surfaced it. Collapsing that into "correct" or "false positive" would
    hide the signal needed to audit retrieval.
    """
    direct = [
        item
        for item in evidence
        if item.polarity == "SUPPORTS" and item.establishes_direct_link
    ]
    real = final_class in {
        RelationshipClass.SHARED_CAUSAL_MECHANISM,
        RelationshipClass.SHARED_DOWNSTREAM_MECHANISM,
        RelationshipClass.SHARED_PROTEIN_COMPLEX,
        RelationshipClass.SHARED_PATHWAY,
    }
    if real:
        # Did the retrieval feature itself carry the relationship? It did only if
        # the pair was anchored on a specific shared molecular feature.
        anchored_strongly = any(
            axis.name in {"SHARED_GENE_OR_PROTEIN", "SHARED_MOLECULAR_FUNCTION"}
            and axis.strength is OverlapStrength.STRONG
            for axis in comparison.axes
        )
        if anchored_strongly:
            return RetrievalValidity.CORRECT
        if direct:
            return RetrievalValidity.INCORRECT_BUT_CONNECTION_REAL
        return RetrievalValidity.PARTIALLY_CORRECT
    if final_class in {
        RelationshipClass.RETRIEVAL_ARTIFACT,
        RelationshipClass.CONTRADICTED,
        RelationshipClass.SHARED_PHENOTYPE_ONLY,
    }:
        return RetrievalValidity.INCORRECT_AND_CONNECTION_FALSE
    if final_class in {
        RelationshipClass.SAME_ALLELIC_SPECTRUM,
        RelationshipClass.SAME_DISEASE_ENTITY,
    }:
        # The feature match was real; it just did not mean what it appeared to.
        return RetrievalValidity.PARTIALLY_CORRECT
    if final_class is RelationshipClass.INSUFFICIENT_EVIDENCE:
        return RetrievalValidity.UNRESOLVED
    return RetrievalValidity.INCOMPLETE


def run_pipeline(
    *,
    pair_id: str,
    candidate: Candidate,
    comparison: DiseaseComparison,
    identity_relation: IdentityRelation,
    identity_rationale: str,
    evidence: tuple[MechanisticEvidence, ...],
    retrieval_reasons: tuple[RetrievalReason, ...],
    source_version: str,
    ontology_versions: dict[str, str] | None = None,
) -> tuple[DecisionTrace, ValidatedRelationship]:
    """Run every stage in order and return the trace plus the relationship."""
    trace = DecisionTrace(
        pair_id=pair_id,
        disease_a=comparison.left_id,
        disease_b=comparison.right_id,
        retrieval_reasons=retrieval_reasons,
    )

    # 1. Identity, before any mechanism claim.
    trace.identity_relation = identity_relation
    trace.record("DiseaseIdentityCheck", f"{identity_relation.value}: {identity_rationale}")

    # 2. Why the pair was retrieved, recorded without judgement.
    reasons = ", ".join(
        f"{item.reason_type.value}({item.source_feature})" for item in retrieval_reasons
    ) or "no retrieval reason recorded"
    trace.record("RetrievalReasonInspection", reasons)

    # 3. Molecular anchor.
    trace.molecular_anchor_present = comparison.has_molecular_anchor
    anchors = [
        f"{axis.name}={axis.strength.value}"
        for axis in comparison.axes
        if axis.name
        in {"SHARED_GENE_OR_PROTEIN", "SHARED_MOLECULAR_FUNCTION", "SHARED_CELLULAR_PROCESS"}
    ]
    trace.molecular_anchor_description = "; ".join(anchors) or "none"
    trace.record(
        "MolecularAnchorInspection",
        f"anchored={comparison.has_molecular_anchor} [{trace.molecular_anchor_description}]",
    )

    # 4. Variant compatibility.
    verdict_map = {
        "COMPATIBLE": CompatibilityVerdict.COMPATIBLE,
        "INCOMPATIBLE": CompatibilityVerdict.INCOMPATIBLE,
        "UNDETERMINED": CompatibilityVerdict.UNKNOWN,
        "NOT_ASSESSABLE": CompatibilityVerdict.UNKNOWN,
    }
    trace.variant_compatibility = verdict_map.get(
        comparison.variant_compatibility.status.value, CompatibilityVerdict.UNKNOWN
    )
    trace.record(
        "VariantEffectCompatibility",
        f"{comparison.variant_compatibility.status.value}: "
        f"{comparison.variant_compatibility.reason}",
        assessable=comparison.variant_compatibility.status.value != "NOT_ASSESSABLE",
    )

    # 5-7. Feature comparisons, each reporting what it could and could not see.
    for stage, axis_name in (
        ("ProcessComparison", "SHARED_CELLULAR_PROCESS"),
        ("CellTypeTissueComparison", "SHARED_CELL_OR_TISSUE"),
        ("PhenotypeComparison", "SHARED_PHENOTYPE"),
    ):
        axis = comparison.axis(axis_name)
        if axis is None:
            trace.record(stage, "no shared features on this axis", assessable=False)
        else:
            labels = ", ".join(axis.shared_labels[:5])
            trace.record(stage, f"{axis.strength.value}: {labels}")

    # 8-9. Evidence, supplied rather than fetched.
    supporting = tuple(i.evidence_id for i in evidence if i.polarity == "SUPPORTS")
    refuting = tuple(i.evidence_id for i in evidence if i.polarity == "REFUTES")
    qualifying = tuple(i.evidence_id for i in evidence if i.polarity == "QUALIFIES")
    trace.supporting_evidence_ids = supporting
    trace.contradicting_evidence_ids = refuting
    trace.qualifying_evidence_ids = qualifying
    trace.record(
        "EvidenceRetrieval",
        f"{len(evidence)} items retrieved" if evidence else "no evidence retrieved",
        assessable=bool(evidence),
    )
    direct_primary = [
        i for i in evidence
        if i.polarity == "SUPPORTS" and i.establishes_direct_link and i.is_primary_finding
    ]
    trace.record(
        "EvidenceFitReview",
        f"{len(direct_primary)} primary findings establish a direct molecular link",
    )
    trace.record(
        "ContradictionSearch",
        f"{len(refuting)} contradicting, {len(qualifying)} qualifying",
    )

    # 10. Alternatives.
    alternatives = generate_alternatives(comparison, identity_relation)
    trace.alternative_explanations = alternatives
    applying = [item.code for item in alternatives if item.applies]
    trace.record(
        "AlternativeExplanationGeneration",
        f"{len(applying)} of {len(alternatives)} alternatives apply: "
        + (", ".join(applying) or "none"),
    )

    # 11. Synthesis.
    final_class, rationale, actionable = classify(comparison, identity_relation, evidence)
    trace.final_relationship_class = final_class
    trace.final_rationale = rationale
    trace.actionable = actionable
    trace.retrieval_validity = assess_retrieval_validity(comparison, final_class, evidence)
    trace.record(
        "MechanisticSynthesis",
        f"{final_class.value} (retrieval {trace.retrieval_validity.value}): {rationale}",
    )

    relationship = ValidatedRelationship(
        relationship_id=f"relationship:{pair_id}",
        disease_a=comparison.left_id,
        disease_b=comparison.right_id,
        relationship_class=final_class,
        mechanistic_statement=rationale,
        retrieval_reason_ids=tuple(i.retrieval_reason_id for i in retrieval_reasons),
        retrieval_validity=trace.retrieval_validity,
        shared_features=tuple(
            label for axis in comparison.axes for label in axis.shared_labels[:3]
        ),
        differing_features=tuple(
            label for _id, label in comparison.phenotypes.distinctive_right[:5]
        ),
        evidence_ids=supporting,
        contradictory_evidence_ids=refuting,
        variant_compatibility=trace.variant_compatibility,
        identity_relation=identity_relation,
        caveats=comparison.caveats,
        alternative_explanations=tuple(
            f"{item.code}: {item.description}" for item in alternatives if item.applies
        ),
        deterministic_status=final_class.value,
        human_review_status=ReviewStatus.AWAITING_EXPERT_SIGNOFF,
        source_version=source_version,
        ontology_versions=ontology_versions or {},
        algorithm_version=PIPELINE_VERSION,
    )
    return trace, relationship


def default_retrieval_reasons(
    candidate: Candidate, disease_a: str, disease_b: str, algorithm_version: str
) -> tuple[RetrievalReason, ...]:
    """Convert the retrieval features into first-class RetrievalReason records."""
    mapping = {
        "SHARED_GENE_OR_PROTEIN": ReasonType.SAME_GENE,
        "SHARED_MOLECULAR_FUNCTION": ReasonType.SHARED_GO_TERM,
        "SHARED_CELLULAR_PROCESS": ReasonType.SHARED_CELLULAR_PROCESS,
        "SHARED_CELL_OR_TISSUE": ReasonType.SHARED_CELL_TYPE,
        "SHARED_PHENOTYPE": ReasonType.PHENOTYPE_SIMILARITY,
    }
    reasons: list[RetrievalReason] = []
    for method, features in sorted(candidate.methods.items()):
        if not features:
            continue
        strongest = features[0]
        reasons.append(
            RetrievalReason.create(
                disease_a=disease_a,
                disease_b=disease_b,
                reason_type=mapping.get(method, ReasonType.OTHER),
                source_feature=strongest.label,
                generating_algorithm="feature-index-retrieval",
                algorithm_version=algorithm_version,
                source_identifier=strongest.feature_id,
                corpus_frequency=strongest.corpus_frequency,
                information_content=strongest.information_content,
            )
        )
    return tuple(reasons)
