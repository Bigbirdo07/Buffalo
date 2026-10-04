"""Turn a validated cross-disease relationship into one gap and one experiment.

The shape of a cross-disease question is always the same, whatever the diseases:
two disorders are reported to converge on some biology, and nobody has applied
one assay to both. So the generator is structural. It reads the relationship's
own shared features, differences and evidence, and names nothing itself.

Two rules it enforces rather than suggests:

**An experiment that cannot fail is rejected.** Every proposal must state the
result that would weaken or refute the shared-mechanism hypothesis, and that
result must be distinguishable from the supporting one. A proposal failing this
check is not returned with a warning; it raises.

**The comparison must be able to separate the hypotheses.** Testing two disease
models without a shared control, or with different readouts, cannot answer
whether the disruption is equivalent, so the generator requires a common readout
and a matched comparator before it will emit anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from atlas.domain.cross_disease import RelationshipClass, ValidatedRelationship
from atlas.domain.experiments import ExperimentProposal
from atlas.domain.gaps import (
    GapPriorityDimensions,
    GapType,
    KnowledgeGap,
    SearchCoverage,
)
from atlas.services.disease_comparison import DiseaseComparison

SYNTHESIS_VERSION = "cross-disease-synthesis-v1"

# Relationship classes worth building a gap on. A negative or identity class has
# no open cross-disease question: the first is answered, the second is not a
# cross-disease question at all.
GAP_WORTHY = frozenset(
    {
        RelationshipClass.SHARED_CAUSAL_MECHANISM,
        RelationshipClass.SHARED_DOWNSTREAM_MECHANISM,
        RelationshipClass.SHARED_PROTEIN_COMPLEX,
        RelationshipClass.SHARED_PATHWAY,
    }
)

DISCLAIMER = "Research proposal requiring expert review."


class NotFalsifiable(ValueError):
    """Raised when a proposal states no result that would weaken its hypothesis."""


@dataclass(frozen=True)
class SynthesisInputs:
    """Everything the generator is allowed to use. No free-text disease knowledge."""

    relationship: ValidatedRelationship
    comparison: DiseaseComparison
    disease_a_name: str
    disease_b_name: str
    # DEPRECATED as a question source: this is the retrieval feature, kept only
    # for context. The gap is built from the bridge below.
    shared_process_label: str
    # Readout that could be applied identically to both, from required capabilities.
    shared_readout: str
    # Model system available for both diseases.
    model_system: str
    supporting_evidence: tuple[str, ...]
    contradicting_evidence: tuple[str, ...]
    # Required, not optional. A gap whose search coverage is unstated invites
    # the reader to assume the search was exhaustive, and "we found nothing"
    # means nothing without knowing where it was looked for.
    coverage: SearchCoverage


def _identity(*parts: str) -> str:
    return str(uuid5(NAMESPACE_URL, "|".join(parts)))


def build_cross_disease_gap(inputs: SynthesisInputs) -> KnowledgeGap:
    """One specific, testable question about whether convergence is functional.

    The question is always the same shape because the uncertainty is: evidence
    shows the two diseases touch one process, and no one has measured whether
    they disrupt it the same way. "More research is needed" is not a gap; "do
    these two produce equivalent disruption of this process, measured the same
    way, in comparable models" is.
    """
    relationship = inputs.relationship
    if relationship.relationship_class not in GAP_WORTHY:
        raise ValueError(
            f"{relationship.relationship_class.value} carries no open "
            "cross-disease mechanistic question; a gap would be manufactured."
        )
    if not relationship.evidence_ids:
        raise ValueError("a cross-disease gap must rest on evidence, not annotation")
    bridge = relationship.mechanistic_bridge
    if bridge is None:
        raise ValueError(
            "a cross-disease gap must be built from the mechanistic bridge the "
            "evidence supports. Without one there is only the retrieval "
            "annotation, and testing that measures the wrong thing."
        )
    # The node to test: what the literature describes, not what surfaced the pair.
    tested_node = bridge.axis_label

    question = (
        f"Do {inputs.disease_a_name} and {inputs.disease_b_name} converge on a "
        f"shared functional defect in {tested_node} in disease-relevant models, "
        "measured with a single shared readout under matched conditions?"
    )

    differences = ", ".join(relationship.differing_features[:4]) or "none recorded"
    contrary = (
        ", ".join(inputs.contradicting_evidence)
        if inputs.contradicting_evidence
        else "No contradicting evidence was retrieved by the recorded searches."
    )

    return KnowledgeGap(
        # Identity includes the bridge: a different mechanistic explanation is
        # a different question, and must not silently reuse the old gap id.
        gap_id=_identity(
            "cross-disease-gap", relationship.relationship_id, bridge.bridge_id,
            "|".join(bridge.terms),
        ),
        question=question,
        # The missing thing is a comparative measurement, so the controlled
        # vocabulary's "missing_assay" is the honest fit. Inventing a new
        # gap type for this shape would fragment the taxonomy for one case.
        gap_type=GapType.MISSING_ASSAY,
        related_claims=(),
        related_edges=(),
        scope=(
            f"{inputs.disease_a_name} and {inputs.disease_b_name}, restricted to "
            f"{tested_node}. The pair was retrieved on "
            f"'{inputs.shared_process_label}', which is broader and is NOT what "
            "is being tested: the question follows the evidence, not the "
            "annotation. The question is equivalence of "
            "functional consequence, not whether either disease involves the "
            "process, which the cited evidence already supports."
        ),
        why_it_matters=(
            "The two diseases are reported to converge on this biology, but no "
            "study has applied one assay to both. Until that is done, every "
            "downstream decision -- whether a model, assay or therapeutic "
            "strategy developed for one disease is informative for the other -- "
            "rests on an assumption rather than a measurement. A negative answer "
            "is as valuable as a positive one: it would stop effort being spent "
            "transferring tools across a boundary they do not cross."
        ),
        current_evidence_summary=(
            f"{len(inputs.supporting_evidence)} corroborating primary findings "
            f"({', '.join(inputs.supporting_evidence)}) establish a direct "
            f"molecular link. {bridge.statement} They do not establish that the "
            "downstream functional consequence is the same in both diseases, and "
            "the supporting reports are limited in number and experimental "
            "context."
        ),
        contradictory_evidence_summary=contrary,
        search_coverage=inputs.coverage,
        missing_evidence_type=(
            "A head-to-head functional comparison: both diseases' models assayed "
            "in parallel, same readout, same control, same laboratory.",
            "Any measurement of the downstream consequence in both diseases, "
            "rather than the molecular interaction alone.",
        ),
        required_context=(
            inputs.model_system,
            f"a readout capturing {tested_node}",
            "matched isogenic or otherwise background-comparable controls",
            "both diseases assayed in the same experiment",
        ),
        priority_reason=GapPriorityDimensions(
            causal_centrality=(
                "The gap sits exactly where the relationship was established: "
                "evidence shows the molecular link, nothing shows the functional "
                "consequence is shared."
            ),
            downstream_dependence=(
                "Every transfer decision depends on it -- whether a model, assay "
                "or therapeutic strategy from one disease informs the other."
            ),
            evidence_conflict=(
                f"Known differences between the diseases ({differences}) mean "
                "equivalence cannot be assumed from the molecular link alone."
            ),
            translational_relevance=(
                "If equivalence holds, research infrastructure built for one "
                "disease becomes testable in the other, which is the scarcest "
                "resource in both communities. If it fails, effort is saved."
            ),
            experimental_tractability=(
                "One assay, two disease arms and a shared control in a single "
                "experiment. No new method is required; the readout already "
                "exists in the field."
            ),
            available_assets=(
                "Requires a model of each disease and one readout able to report "
                "the shared process. Whether these exist for both diseases is "
                "established by discovery, not assumed here."
            ),
            discriminates_competing_hypotheses=(
                "Yes. Equivalent disruption supports shared mechanism; opposite "
                "direction, absent effect in one arm, or magnitudes beyond the "
                "within-genotype range support non-equivalence. The two outcomes "
                "are distinguishable by the same measurement."
            ),
        ),
        resolvability=(
            "Experimentally resolvable. The discriminating measurement is "
            f"{inputs.shared_readout} applied to models of both diseases and a "
            "shared control in one experiment."
        ),
        proposed_discriminating_test=(
            "Apply one assay to models of both diseases and a shared control in "
            "the same experiment, and compare the direction and magnitude of the "
            "effect."
        ),
        status="OPEN",
    )


def tested_node_for(inputs: SynthesisInputs) -> str:
    """The biology the experiment measures: the bridge, never the annotation."""
    bridge = inputs.relationship.mechanistic_bridge
    if bridge is None:
        raise ValueError(
            "no mechanistic bridge, so there is nothing evidence-supported to "
            "test. Testing the retrieval annotation instead would measure a "
            "process both diseases touch while missing where they meet."
        )
    return bridge.axis_label


def build_cross_disease_experiment(
    gap: KnowledgeGap, inputs: SynthesisInputs
) -> ExperimentProposal:
    """One falsifiable head-to-head experiment, or an exception.

    The design is deliberately the simplest that can answer the question: both
    diseases' models, a shared control, one readout, one run. Adding arms would
    make it more informative and less likely to be done.
    """
    tested_node = tested_node_for(inputs)
    supported = (
        f"Both disease models show disruption of {tested_node} "
        "in the same direction, of comparable magnitude, relative to the shared "
        "control. This supports functional equivalence at the measured step and "
        "makes tools developed for one disease worth testing in the other."
    )
    refuted = (
        f"The two disease models differ in the direction of the effect, or one "
        f"shows no detectable disruption of {tested_node} while "
        "the other does, or the magnitudes differ beyond the range seen between "
        "replicate clones of a single genotype. Any of these weakens the "
        "shared-mechanism hypothesis: the diseases would touch the same process "
        "without disrupting it equivalently, and tools should not be transferred "
        "between them on this basis."
    )

    proposal = ExperimentProposal(
        experiment_id=_identity("cross-disease-experiment", gap.gap_id),
        knowledge_gap_id=gap.gap_id,
        scientific_question=gap.question,
        hypothesis=(
            f"{inputs.disease_a_name} and {inputs.disease_b_name} disrupt "
            f"{tested_node} equivalently, so the same functional "
            "readout reports the same defect in both."
        ),
        competing_hypothesis=(
            "The diseases share the molecular interaction the evidence "
            "describes, and a broad process annotation, while diverging "
            "functionally downstream. Under this hypothesis the link is real but "
            "the mechanisms are not equivalent, and tools should not be "
            "transferred between the diseases on the strength of it."
        ),
        model_system=inputs.model_system,
        sample_type=(
            "Patient-derived or engineered models representing each disease, "
            "plus a shared control of the same genetic background."
        ),
        patient_stratification=(
            "Genotypes representative of each disease",
            "Neither arm represented solely by a variant of uncertain significance",
        ),
        perturbation=(
            "A standardised cellular stress applied identically to every arm. "
            "The bridge describes stress-responsive biology, so a baseline-only "
            "comparison could miss a defect that appears only when the pathway "
            "is challenged, and a null result would then be uninterpretable."
        ),
        comparator=(
            "A single shared control run in the same experiment as both disease "
            "arms. Separate per-disease controls would make the arms "
            "incomparable, which is the failure this design exists to avoid."
        ),
        controls=(
            "Isogenic or background-matched control",
            "Replicate clones per genotype, to establish the within-genotype "
            "range the between-disease comparison must exceed",
            "A positive control that perturbs the readout by a known route",
        ),
        readouts=(
            # Primary: the functional behaviour of the bridged node itself.
            f"Functional response of {tested_node} to the standardised stress, "
            "measured identically in every arm",
            # Supporting: molecular profiling. Retained because it is useful,
            # demoted because it defines a broad process rather than the node
            # the evidence actually supports.
            f"{inputs.shared_readout} as a supporting molecular profile, "
            "interpreted only alongside the primary functional readout",
        ),
        primary_endpoint=(
            f"Direction and magnitude of the {tested_node} response to stress in "
            "each disease arm relative to the shared control."
        ),
        secondary_endpoints=(
            "Concordance between the functional response and the supporting "
            "molecular profile within each arm.",
        ),
        expected_result_if_supported=supported,
        expected_result_if_refuted=refuted,
        confounders=(
            "Clone-to-clone variation can exceed the between-disease difference; "
            "the replicate-clone control exists to bound it.",
            "Differing model maturity or culture age between arms can produce a "
            "difference unrelated to genotype.",
            "If the two diseases' models cannot be cultured identically, any "
            "difference is confounded by protocol rather than biology.",
        ),
        known_limitations=(
            "A single readout at one timepoint cannot exclude equivalence that "
            "emerges, or disappears, over time.",
            "A negative result constrains equivalence at the measured step only "
            "and does not exclude shared biology elsewhere.",
            "Model systems may not reproduce the cell type where the diseases "
            "actually diverge.",
        ),
        # Stated by the experiment, so the requirement extractor reads them from
        # the design rather than inferring them. Each is derived from a decision
        # the design actually makes: two disease arms imply two models, one
        # shared readout implies that assay, a shared control implies matched
        # material, and replicate clones imply clone-aware statistics.
        required_assets=(
            f"Cellular model of {inputs.disease_a_name}",
            f"Cellular model of {inputs.disease_b_name}",
            "Background-matched control line shared by both arms",
            f"Assay reagents for {inputs.shared_readout}",
        ),
        required_capabilities=(
            f"Functional assay reporting {tested_node} under standardised stress",
            "Cellular stress / heat-shock challenge applied identically across arms",
            "iPSC maintenance and differentiation to the disease-relevant cell type",
            "Clone-aware statistical analysis establishing the within-genotype range",
            f"{inputs.shared_readout} for supporting molecular profiling",
        ),
        safety_or_ethics_flags=(),
        unjustified_interpretations=(
            "That equivalence at this step implies a shared treatment response.",
            "That a difference here means the diseases are mechanistically "
            "unrelated; it means they are not equivalent at this step.",
            "That any result establishes causation in patients, since the "
            "measurement is made in models.",
        ),
        human_review_required=True,
        label=DISCLAIMER,
    )
    assert_falsifiable(proposal)
    return proposal


def assert_falsifiable(proposal: ExperimentProposal) -> None:
    """Refuse a proposal that cannot fail.

    Checked rather than trusted, because an experiment with no refutation
    condition is the easiest thing for a generator to produce and the least
    useful thing for a scientist to receive. A proposal that merely restates the
    supporting result as its refutation is caught by the distinguishability
    check.
    """
    refuted = (proposal.expected_result_if_refuted or "").strip()
    supported = (proposal.expected_result_if_supported or "").strip()
    if not refuted:
        raise NotFalsifiable(
            f"{proposal.experiment_id} states no result that would weaken the "
            "hypothesis. An experiment that cannot fail must not be proposed."
        )
    if refuted.casefold() == supported.casefold():
        raise NotFalsifiable(
            f"{proposal.experiment_id} gives the same text for the supporting and "
            "refuting outcomes, so no result could distinguish them."
        )
    if not proposal.comparator.strip() or not proposal.readouts:
        raise NotFalsifiable(
            f"{proposal.experiment_id} lacks a comparator or a readout, so its "
            "arms cannot be compared and no outcome is interpretable."
        )
