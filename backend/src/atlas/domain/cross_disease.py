"""Cross-disease relationships, with retrieval kept strictly apart from evidence.

This module exists because of a measured failure in this system, not a
hypothetical one. Lafora disease was retrieved as a neighbour of SCAR16 on a
shared "protein ubiquitination" annotation. The pair turned out to be real --
CHIP physically binds and stabilises malin, and the two sit in one heat-shock
complex -- but *not for the annotated reason*: malin ubiquitinates glycogen
enzymes while CHIP triages chaperone clients. The system had found its best lead
through a term that does not explain it, and its own ranking called that lead
unanchored.

Two conclusions are built into the types here.

**A retrieval reason is not evidence.** `RetrievalReason` records why an
algorithm surfaced a pair. It carries no evidence ids and no biological claim,
and no code path turns one into a `ValidatedRelationship`. The second is produced
only by the refinement engine reading literature.

**The two can disagree, and that disagreement is information.** A pair can be
retrieved for a wrong reason and still be real; retrieved for a right reason and
still be spurious. `RetrievalValidity` records which happened, so the atlas can
say "we found these because they share an annotation, but the real connection is
different" -- and so the retrieval algorithm can be audited against outcomes
rather than trusted.

Nothing here is specific to any disease, gene or pathway. The cases above are
regression fixtures, never rules.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

RELATIONSHIP_ONTOLOGY_VERSION = "cross-disease-relationship-v1"


def _identity(*parts: str) -> str:
    return str(uuid5(NAMESPACE_URL, "|".join(parts)))


class ReasonType(StrEnum):
    """Why an algorithm surfaced a pair. A computational fact, not a claim."""

    SAME_GENE = "SAME_GENE"
    GENE_FAMILY = "GENE_FAMILY"
    SHARED_PROTEIN_COMPLEX = "SHARED_PROTEIN_COMPLEX"
    SHARED_PATHWAY = "SHARED_PATHWAY"
    SHARED_GO_TERM = "SHARED_GO_TERM"
    SHARED_CELLULAR_PROCESS = "SHARED_CELLULAR_PROCESS"
    SHARED_CELL_TYPE = "SHARED_CELL_TYPE"
    SHARED_TISSUE = "SHARED_TISSUE"
    PHENOTYPE_SIMILARITY = "PHENOTYPE_SIMILARITY"
    HPO_SEMANTIC_SIMILARITY = "HPO_SEMANTIC_SIMILARITY"
    ORTHOLOG_PHENOTYPE_SIMILARITY = "ORTHOLOG_PHENOTYPE_SIMILARITY"
    EMBEDDING_SIMILARITY = "EMBEDDING_SIMILARITY"
    GRAPH_NEIGHBORHOOD = "GRAPH_NEIGHBORHOOD"
    THERAPEUTIC_MODALITY_OVERLAP = "THERAPEUTIC_MODALITY_OVERLAP"
    LITERATURE_SEMANTIC_MATCH = "LITERATURE_SEMANTIC_MATCH"
    OTHER = "OTHER"


class RelationshipClass(StrEnum):
    """What the evidence says the relationship actually is."""

    SAME_DISEASE_ENTITY = "SAME_DISEASE_ENTITY"
    SAME_ALLELIC_SPECTRUM = "SAME_ALLELIC_SPECTRUM"
    OVERLAPPING_PHENOTYPIC_SPECTRUM = "OVERLAPPING_PHENOTYPIC_SPECTRUM"
    SHARED_CAUSAL_MECHANISM = "SHARED_CAUSAL_MECHANISM"
    SHARED_DOWNSTREAM_MECHANISM = "SHARED_DOWNSTREAM_MECHANISM"
    SHARED_PROTEIN_COMPLEX = "SHARED_PROTEIN_COMPLEX"
    SHARED_PATHWAY = "SHARED_PATHWAY"
    SHARED_CELLULAR_PROCESS_NON_EQUIVALENT = "SHARED_CELLULAR_PROCESS_NON_EQUIVALENT"
    SHARED_CELL_STATE = "SHARED_CELL_STATE"
    SHARED_TISSUE_CONTEXT = "SHARED_TISSUE_CONTEXT"
    SHARED_PHENOTYPE_ONLY = "SHARED_PHENOTYPE_ONLY"
    MODEL_ORGANISM_ANALOG = "MODEL_ORGANISM_ANALOG"
    POTENTIAL_THERAPEUTIC_ANALOG = "POTENTIAL_THERAPEUTIC_ANALOG"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONTEXT_DEPENDENT = "CONTEXT_DEPENDENT"
    CONTRADICTED = "CONTRADICTED"
    RETRIEVAL_ARTIFACT = "RETRIEVAL_ARTIFACT"
    UNKNOWN = "UNKNOWN"


# Classes asserting that two diseases share biology at a mechanistic level.
# Reaching one of these requires evidence beyond annotation overlap.
MECHANISTIC_CLASSES = frozenset(
    {
        RelationshipClass.SHARED_CAUSAL_MECHANISM,
        RelationshipClass.SHARED_DOWNSTREAM_MECHANISM,
        RelationshipClass.SHARED_PROTEIN_COMPLEX,
        RelationshipClass.SHARED_PATHWAY,
    }
)
# Classes meaning "these are not two independent diseases".
IDENTITY_CLASSES = frozenset(
    {
        RelationshipClass.SAME_DISEASE_ENTITY,
        RelationshipClass.SAME_ALLELIC_SPECTRUM,
        RelationshipClass.OVERLAPPING_PHENOTYPIC_SPECTRUM,
    }
)
# Classes that are a negative result. Preserved, never deleted: a rejected edge
# is evidence that similar phenotype does not imply shared mechanism.
NEGATIVE_CLASSES = frozenset(
    {
        RelationshipClass.SHARED_PHENOTYPE_ONLY,
        RelationshipClass.SHARED_CELLULAR_PROCESS_NON_EQUIVALENT,
        RelationshipClass.CONTRADICTED,
        RelationshipClass.RETRIEVAL_ARTIFACT,
    }
)


class RetrievalValidity(StrEnum):
    """Whether the algorithm's stated reason survived contact with evidence.

    INCORRECT_BUT_CONNECTION_REAL is the value that motivated this module: the
    pair is genuine and the explanation is wrong. Collapsing it into either
    "correct" or "false positive" destroys the signal needed to improve
    retrieval, and lets a wrong explanation travel as if it were the finding.
    """

    CORRECT = "CORRECT"
    PARTIALLY_CORRECT = "PARTIALLY_CORRECT"
    INCOMPLETE = "INCOMPLETE"
    INCORRECT_BUT_CONNECTION_REAL = "INCORRECT_BUT_CONNECTION_REAL"
    INCORRECT_AND_CONNECTION_FALSE = "INCORRECT_AND_CONNECTION_FALSE"
    UNRESOLVED = "UNRESOLVED"


class CompatibilityVerdict(StrEnum):
    COMPATIBLE = "COMPATIBLE"
    PARTIALLY_COMPATIBLE = "PARTIALLY_COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


class IdentityRelation(StrEnum):
    """Whether two labels denote independent diseases at all."""

    SAME_DISEASE = "SAME_DISEASE"
    ALLELIC_SPECTRUM = "ALLELIC_SPECTRUM"
    PHENOTYPIC_SUBTYPE = "PHENOTYPIC_SUBTYPE"
    HISTORICAL_SYNONYM = "HISTORICAL_SYNONYM"
    PARTIALLY_OVERLAPPING_ENTITY = "PARTIALLY_OVERLAPPING_ENTITY"
    DISTINCT_DISEASE = "DISTINCT_DISEASE"


class ReviewStatus(StrEnum):
    NOT_REVIEWED = "NOT_REVIEWED"
    AWAITING_EXPERT_SIGNOFF = "AWAITING_EXPERT_SIGNOFF"
    ACCEPTED = "ACCEPTED"
    AMENDED = "AMENDED"
    REJECTED = "REJECTED"


# Words that assert a stronger relationship than a term list supports. A display
# label is a rendering, not a claim, so introducing any of these would smuggle a
# conclusion into what is meant to be a name.
_CAUSAL_ESCALATION = frozenset(
    {
        "causes", "caused", "causing", "drives", "driven", "leads to",
        "results in", "responsible for", "equivalent", "identical", "same as",
        "proves", "proven", "establishes", "confirms", "demonstrates",
        "shared mechanism", "mechanistically equivalent",
    }
)
# Split on hyphens too: "CHIP-associated" is the word "CHIP" joined to the
# connective "associated", and treating it as one unknown token would
# reject a rendering that adds nothing.
_WORD_PATTERN = __import__("re").compile(r"[a-z0-9]+")


def validate_display_label(label: str, terms: tuple[str, ...]) -> None:
    """Refuse a label that claims more than its canonical terms.

    A display label exists so a reader is not handed a comma-separated list. It
    must stay replaceable without changing the scientific object, which means it
    may simplify wording and may not introduce an entity, a direction or a
    causal claim the terms do not carry.

    Checked rather than trusted, because a nicer label is exactly the kind of
    change that gets made late and reviewed lightly.
    """
    lowered = label.casefold()
    for phrase in _CAUSAL_ESCALATION:
        if phrase in lowered:
            raise ValueError(
                f"display label asserts {phrase!r}, which the canonical terms do "
                "not support. A label may rename, not conclude."
            )
    allowed: set[str] = set()
    for term in terms:
        allowed.update(_WORD_PATTERN.findall(term.casefold()))
    # Connective vocabulary a readable phrase needs, carrying no claim.
    allowed.update(
        {
            "and", "or", "of", "the", "a", "an", "in", "with", "associated",
            "related", "biology", "axis", "pathway", "process", "node",
            "machinery", "system", "activity", "function", "control", "quality",
        }
    )
    unsupported = [
        word for word in _WORD_PATTERN.findall(lowered) if word not in allowed
    ]
    if unsupported:
        raise ValueError(
            f"display label introduces {unsupported!r}, which no canonical term "
            "supports. Entities may not be added by a rendering."
        )


class EvidenceDepth(StrEnum):
    """How deeply the evidence behind a bridge was actually read.

    Recorded on the bridge itself so the limitation travels with the claim. A
    bridge built from abstracts is not wrong, but every downstream reader is
    entitled to know that no one opened the papers.
    """

    FULL_TEXT_REVIEWED = "FULL_TEXT_REVIEWED"
    ABSTRACT_OR_DERIVED_SOURCE = "ABSTRACT_OR_DERIVED_SOURCE"
    TITLE_ONLY = "TITLE_ONLY"
    UNKNOWN = "UNKNOWN"


class CapabilityRecency(StrEnum):
    """How recently a capability was demonstrated.

    Historical evidence is not rejected: a team that ran an assay years ago may
    still run it. The classification exists to say what must be checked, not to
    discard a candidate.
    """

    CURRENT = "CURRENT"
    RECENT = "RECENT"
    HISTORICAL = "HISTORICAL"
    UNKNOWN = "UNKNOWN"


class ModelAvailability(StrEnum):
    """Existence and availability are different facts about a research model.

    A paper using a model proves it existed in that study. It proves nothing
    about whether the model is deposited, shareable, or still maintained, and
    conflating the two would send a patient organisation chasing material that
    may no longer exist.
    """

    MODEL_DEMONSTRATED = "MODEL_DEMONSTRATED"
    MODEL_REPOSITORY_VERIFIED = "MODEL_REPOSITORY_VERIFIED"
    MODEL_CURRENT_AVAILABILITY_UNKNOWN = "MODEL_CURRENT_AVAILABILITY_UNKNOWN"
    MODEL_NOT_LOCATED = "MODEL_NOT_LOCATED"


class CoverageStatus2(StrEnum):
    """Whether a required capability is covered, and how well."""

    COVERED_VERIFIED = "COVERED_VERIFIED"
    COVERED_SUPPORTED = "COVERED_SUPPORTED"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"


class CollaborationTopology(StrEnum):
    SINGLE_GROUP_EXECUTABLE = "SINGLE_GROUP_EXECUTABLE"
    MULTI_PARTY_EXECUTABLE = "MULTI_PARTY_EXECUTABLE"
    PARTIALLY_EXECUTABLE = "PARTIALLY_EXECUTABLE"
    NOT_CURRENTLY_EXECUTABLE = "NOT_CURRENTLY_EXECUTABLE"


class PotentialCoordinationOpportunity(BaseModel):
    """Two groups whose work may overlap. A question, never an accusation.

    Never asserts duplication. Two groups pursuing related work may be
    collaborating, replicating deliberately, or approaching the same problem
    differently, and a system that called that waste would be both wrong and
    damaging.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunity_id: str
    group_a: str
    group_b: str
    overlapping_objective: str
    overlapping_capability: str
    evidence_ids: tuple[str, ...]
    uncertainty: str
    potential_benefit: str
    verification_required: str
    status: str = "POTENTIAL_COORDINATION_OPPORTUNITY"

    def model_post_init(self, _context: object) -> None:
        if not self.evidence_ids:
            raise ValueError(
                "a coordination opportunity needs evidence of actual overlap; "
                "without it this is speculation about other people's work"
            )


class BridgeTermProvenance(BaseModel):
    """Where one bridge term came from and what kind of statement supported it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    term: str
    source_id: str
    # The sentence the term was read from, kept verbatim so a reviewer can
    # disagree with the reading rather than only with the conclusion.
    span: str
    annotation_type: str
    finding_role: str
    section: str
    snapshot_sha256: str | None = None

    @property
    def is_primary(self) -> bool:
        return self.finding_role == "PRIMARY_EXPERIMENTAL_RESULT"


class MechanisticBridge(BaseModel):
    """What the EVIDENCE says connects two diseases, in the evidence's own terms.

    The third level, and the one that was missing. A pair has:

      * a retrieval reason -- the annotation that surfaced it
      * a mechanistic bridge -- what the retrieved literature actually describes
      * an experimental hypothesis -- what a test would resolve

    These are routinely different, and conflating the first two is the specific
    error this object prevents. A pair found through a broad process annotation
    whose literature describes a narrow molecular axis must be *tested* at the
    narrow axis: testing the broad annotation measures the wrong thing and can
    return a null result for a relationship that is real.

    Terms are extracted from the supporting evidence rather than from the
    annotation, so the bridge cannot inherit the retrieval feature's breadth.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    bridge_id: str
    # Monotonic within a pair. A refinement never edits an earlier version: it
    # creates a new one naming its parent, so the reasoning that produced the
    # original answer stays inspectable after the answer changes.
    version: int = 1
    supersedes_bridge_id: str | None = None
    refinement_reason: str | None = None
    # Source-faithful terms, exactly as the evidence supports them. This layer is
    # never edited for readability.
    terms: tuple[str, ...]
    # The evidence the bridge was read from. Never empty: a bridge with no
    # evidence is a retrieval reason wearing a different name.
    derived_from_evidence_ids: tuple[str, ...]
    statement: str
    derivation_method: str
    # How deeply the supporting evidence was read. Frozen onto the bridge so the
    # limitation cannot be lost downstream.
    evidence_depth: EvidenceDepth = EvidenceDepth.UNKNOWN
    full_text_review_completed: bool = False
    # Per-term provenance: which source, which span, what role that statement
    # played in its paper.
    term_provenance: tuple[BridgeTermProvenance, ...] = ()
    # Optional human-readable rendering. It may simplify wording; it may not
    # change what is claimed. validate_display_label enforces that.
    display_label_override: str | None = None
    # Retrieval features this bridge is distinct from, recorded so the
    # separation is visible rather than asserted.
    distinct_from_retrieval_features: tuple[str, ...] = ()

    def model_post_init(self, _context: object) -> None:
        if not self.derived_from_evidence_ids:
            raise ValueError(
                "a mechanistic bridge must be derived from evidence; without it "
                "this is a retrieval reason under another name"
            )

    @property
    def functional_node(self) -> str:
        """The smallest defensible thing an experiment can actually measure.

        A bridge is a set of terms; an assay measures one node. Listing every
        term as the readout describes a research area rather than a measurement,
        so this picks the most specific functional claim available: a named
        regulator paired with the process it acts in, preferring terms backed by
        a primary finding over ones carried along from the retrieval level.

        General by construction -- it reads whichever terms the evidence
        produced and names nothing itself.
        """
        preferred = self.primary_terms or self.terms
        regulators = [item for item in preferred if item.isupper()]
        processes = [item for item in preferred if not item.isupper()]
        # The most specific process term is the longest: "stress response" says
        # more than "response", "protein quality control" more than "control".
        process = max(processes, key=len) if processes else ""
        if regulators and process:
            return f"{regulators[0]}-dependent {process}"
        if regulators:
            return f"{regulators[0]} activity"
        return process or "the bridged molecular node"

    @property
    def primary_terms(self) -> tuple[str, ...]:
        """Terms backed by a statement the paper claims as its own finding."""
        primary = {item.term for item in self.term_provenance if item.is_primary}
        return tuple(term for term in self.terms if term in primary)

    @property
    def display_label(self) -> str:
        """Readable rendering, validated before use."""
        if self.display_label_override:
            validate_display_label(self.display_label_override, self.terms)
            return self.display_label_override
        return self.axis_label

    @property
    def axis_label(self) -> str:
        """The bridge as a readable biological phrase rather than a term list.

        Process terms describe the axis; uppercase tokens are the regulators
        named in the evidence and are shown in parentheses, because "chaperone
        and co-chaperone biology (CHIP)" is a claim a reader can check while a
        comma-separated list is not.
        """
        processes = [item for item in self.terms if not item.isupper()]
        factors = [item for item in self.terms if item.isupper()]
        if not processes:
            return ", ".join(factors) or "an unnamed molecular axis"
        if len(processes) == 1:
            axis = processes[0]
        else:
            axis = f"{', '.join(processes[:-1])} and {processes[-1]}"
        axis = f"{axis} biology"
        return f"{axis} ({', '.join(factors[:3])})" if factors else axis

    @property
    def is_narrower_than_retrieval(self) -> bool:
        """True when the bridge says something the retrieval feature did not."""
        retrieval = {item.casefold() for item in self.distinct_from_retrieval_features}
        return any(term.casefold() not in retrieval for term in self.terms)


class RetrievalReason(BaseModel):
    """Why an algorithm surfaced a candidate pair.

    Deliberately carries no evidence ids and no biological assertion. It is an
    explanation of a computation, and is never sufficient grounds for any
    relationship class.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    retrieval_reason_id: str
    disease_a: str
    disease_b: str
    reason_type: ReasonType
    source_feature: str
    source_identifier: str | None = None
    # How specific the matched feature is in this corpus. A feature shared by
    # hundreds of diseases explains a research area, not a relationship.
    corpus_frequency: int | None = None
    information_content: float | None = None
    similarity_component: float | None = None
    generating_algorithm: str
    algorithm_version: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        *,
        disease_a: str,
        disease_b: str,
        reason_type: ReasonType,
        source_feature: str,
        generating_algorithm: str,
        algorithm_version: str,
        **extra: object,
    ) -> RetrievalReason:
        left, right = sorted((disease_a, disease_b))
        return cls(
            retrieval_reason_id=_identity(
                "retrieval", left, right, reason_type.value, source_feature,
                algorithm_version,
            ),
            disease_a=left,
            disease_b=right,
            reason_type=reason_type,
            source_feature=source_feature,
            generating_algorithm=generating_algorithm,
            algorithm_version=algorithm_version,
            **extra,  # type: ignore[arg-type]
        )

    @property
    def is_biological_evidence(self) -> bool:
        """Always False. Present so the distinction is executable, not advisory."""
        return False


class ScopedIdentity(BaseModel):
    """An identity verdict that holds only within one causal scope.

    Disease identity is not always a single answer. A genetically heterogeneous
    entity can be a distinct disease from a narrow one overall, while being the
    *same* entity when restricted to the gene they share. Collapsing that to one
    label loses whichever half is inconvenient: call it distinct and a subtype
    relationship is counted as a cross-disease discovery; call it the same and a
    real relationship to the rest of the broad entity disappears.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope_feature: str
    scope_label: str
    relation: IdentityRelation
    rationale: str


class DiseaseIdentityRelationship(BaseModel):
    """Whether two disease labels are independent entities.

    Checked before any cross-disease claim, because two labels for one allelic
    spectrum are a data-model question, not a discovery. Counting them as
    cross-disease findings inflates novelty.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    identity_id: str
    disease_a: str
    disease_b: str
    relation: IdentityRelation
    shared_gene_ids: tuple[str, ...] = ()
    rationale: str
    # Verdicts that hold only within a narrower causal scope. The top-level
    # relation describes the entities as upstream defines them; these describe
    # them restricted to a shared cause.
    scoped: tuple[ScopedIdentity, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    review_status: ReviewStatus = ReviewStatus.NOT_REVIEWED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def has_same_entity_scope(self) -> bool:
        """True when some scope makes these one entity, whatever the top relation.

        A pair with such a scope must not be counted as an independent
        cross-disease discovery for that scope, even when the broad entities
        differ.
        """
        return any(
            item.relation
            in {
                IdentityRelation.SAME_DISEASE,
                IdentityRelation.ALLELIC_SPECTRUM,
                IdentityRelation.PHENOTYPIC_SUBTYPE,
                IdentityRelation.HISTORICAL_SYNONYM,
            }
            for item in self.scoped
        )

    @property
    def is_independent_pair(self) -> bool:
        return (
            self.relation
            in {
                IdentityRelation.DISTINCT_DISEASE,
                IdentityRelation.PARTIALLY_OVERLAPPING_ENTITY,
            }
            and not self.has_same_entity_scope
        )


class ValidatedRelationship(BaseModel):
    """What the evidence says, produced only by the refinement engine.

    A mechanistic class requires evidence ids: the model refuses to construct
    one without them, so "shared mechanism" cannot be asserted on annotation
    overlap through any code path.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    relationship_id: str
    disease_a: str
    disease_b: str
    relationship_class: RelationshipClass
    # Plain statement of what is shared. Empty when nothing is.
    mechanistic_statement: str
    # The retrieval reasons that surfaced this pair, kept so the explanation can
    # be audited against the outcome.
    retrieval_reason_ids: tuple[str, ...] = ()
    retrieval_validity: RetrievalValidity = RetrievalValidity.UNRESOLVED
    # What the evidence says connects these diseases, as distinct from what
    # surfaced them. Downstream questions must be built from this, not from the
    # retrieval feature.
    mechanistic_bridge: MechanisticBridge | None = None
    shared_features: tuple[str, ...] = ()
    differing_features: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    contradictory_evidence_ids: tuple[str, ...] = ()
    variant_compatibility: CompatibilityVerdict = CompatibilityVerdict.UNKNOWN
    cell_type_compatibility: CompatibilityVerdict = CompatibilityVerdict.UNKNOWN
    tissue_compatibility: CompatibilityVerdict = CompatibilityVerdict.UNKNOWN
    directionality_compatibility: CompatibilityVerdict = CompatibilityVerdict.UNKNOWN
    model_compatibility: CompatibilityVerdict = CompatibilityVerdict.UNKNOWN
    identity_relation: IdentityRelation | None = None
    # True when some causal scope makes these one entity, even if the broad
    # entities differ. Such a pair is a subtype relationship within that scope
    # and must not be counted as an independent cross-disease discovery.
    identity_has_same_entity_scope: bool = False
    scoped_identities: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()
    alternative_explanations: tuple[str, ...] = ()
    deterministic_status: str | None = None
    critic_status: str | None = None
    critic_model: str | None = None
    critic_prompt_version: str | None = None
    human_review_status: ReviewStatus = ReviewStatus.NOT_REVIEWED
    # Provenance sufficient to reproduce the relationship.
    source_version: str
    ontology_versions: dict[str, str] = Field(default_factory=dict)
    algorithm_version: str = RELATIONSHIP_ONTOLOGY_VERSION
    # Prior classifications, never overwritten silently.
    superseded_classes: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_reviewed_at: datetime | None = None

    def model_post_init(self, _context: object) -> None:
        if self.relationship_class in MECHANISTIC_CLASSES and not self.evidence_ids:
            raise ValueError(
                f"{self.relationship_class.value} asserts shared biology and "
                "requires evidence_ids. Annotation overlap alone is a retrieval "
                "reason, not evidence."
            )

    @property
    def asserts_shared_mechanism(self) -> bool:
        return self.relationship_class in MECHANISTIC_CLASSES

    @property
    def is_independent_discovery(self) -> bool:
        """True only for a genuine relationship between two distinct diseases."""
        if self.identity_has_same_entity_scope:
            return False
        return (
            self.relationship_class in MECHANISTIC_CLASSES
            and self.relationship_class not in IDENTITY_CLASSES
            and self.identity_relation
            not in {
                IdentityRelation.SAME_DISEASE,
                IdentityRelation.ALLELIC_SPECTRUM,
                IdentityRelation.HISTORICAL_SYNONYM,
                IdentityRelation.PHENOTYPIC_SUBTYPE,
            }
        )

    @property
    def retrieval_explanation_was_wrong(self) -> bool:
        return self.retrieval_validity in {
            RetrievalValidity.INCORRECT_BUT_CONNECTION_REAL,
            RetrievalValidity.INCORRECT_AND_CONNECTION_FALSE,
        }

    def supersede(
        self, new_class: RelationshipClass, **changes: object
    ) -> ValidatedRelationship:
        """Reclassify while keeping the prior class on the record."""
        payload = self.model_dump()
        payload.update(changes)
        payload["relationship_class"] = new_class
        payload["superseded_classes"] = (
            *self.superseded_classes,
            self.relationship_class.value,
        )
        payload["last_reviewed_at"] = datetime.now(UTC)
        return ValidatedRelationship(**payload)


class RejectedCrossDiseaseCandidate(BaseModel):
    """A candidate the evidence did not support.

    Kept rather than discarded. A rejected edge is a benchmark case and a
    demonstration that similar phenotype does not imply shared mechanism; a
    system that only stores its successes cannot measure its own precision.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    rejection_id: str
    disease_a: str
    disease_b: str
    retrieval_reason_ids: tuple[str, ...]
    rejected_class: RelationshipClass
    retrieval_validity: RetrievalValidity
    reason: str
    evidence_ids: tuple[str, ...] = ()
    null_searches: tuple[str, ...] = ()
    review_status: ReviewStatus = ReviewStatus.NOT_REVIEWED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
