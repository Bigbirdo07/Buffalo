"""Choose which validated relationship to carry forward, and say why.

The previous rule ranked by corroboration count, which is wrong: the number of
papers co-mentioning two diseases measures how much they have been written about
together, not how well the mechanism is understood. Under that rule a pair whose
evidence was broad and diffuse outranked one whose evidence was specific and
directly demonstrated.

This replaces it with named components, each computed from evidence the system
already holds and each persisted alongside the decision. There is no blended
score presented as the reason: the components *are* the reason, and a reader who
disagrees can point at the one they think is wrong.

Hard exclusions run first, because some candidates are not eligible at all --
two labels for one disease, a retrieval artifact, or a mechanism claim with no
nameable bridge. Ranking an ineligible candidate well would be worse than
ranking it badly.

Nothing here names a disease, gene or pathway.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SELECTION_VERSION = "flagship-selection-v2"

# Classes that cannot be a flagship cross-disease relationship, with the reason
# stated rather than implied.
HARD_EXCLUSIONS: dict[str, str] = {
    "SAME_DISEASE_ENTITY": "the two labels denote one disease",
    "SAME_ALLELIC_SPECTRUM": "one allelic spectrum under two names, not a cross-disease finding",
    "OVERLAPPING_PHENOTYPIC_SPECTRUM": "overlapping entities rather than distinct diseases",
    "RETRIEVAL_ARTIFACT": "nothing beyond annotation connects these diseases",
    "CONTRADICTED": "the evidence argues against the relationship",
    "SHARED_PHENOTYPE_ONLY": "symptom overlap with no molecular basis",
    "INSUFFICIENT_EVIDENCE": "the evidence does not establish a relationship",
    "SHARED_TISSUE_CONTEXT": "comparable tissue with no demonstrated molecular link",
    "SHARED_CELLULAR_PROCESS_NON_EQUIVALENT": "shared process without demonstrated equivalence",
    "UNKNOWN": "no relationship class was determined",
}

# Ontology vocabulary broad enough that sharing it says little. A bridge resting
# only on these is generic, whatever its evidence count.
GENERIC_TERMS = frozenset(
    {
        "ubiquitination", "phosphorylation", "protein ubiquitination",
        "transcriptional activation", "protein-protein interaction",
        "complex formation", "protein stability", "protein turnover",
        "regulation", "signaling", "metabolism",
    }
)


@dataclass(frozen=True)
class Component:
    """One named, explainable contribution to the decision."""

    name: str
    value: float
    weight: float
    rationale: str

    @property
    def contribution(self) -> float:
        return round(self.value * self.weight, 4)


@dataclass
class CandidateAssessment:
    disease_id: str
    disease_name: str
    relationship_class: str
    eligible: bool
    exclusion_reason: str | None = None
    components: list[Component] = field(default_factory=list)
    penalties: list[Component] = field(default_factory=list)

    @property
    def total(self) -> float:
        gained = sum(item.contribution for item in self.components)
        lost = sum(item.contribution for item in self.penalties)
        return round(gained - lost, 4)

    @property
    def explanation(self) -> str:
        if not self.eligible:
            return f"Excluded: {self.exclusion_reason}"
        parts = [f"{c.name} {c.value:.2f}" for c in self.components if c.value]
        hits = [f"-{p.name} {p.value:.2f}" for p in self.penalties if p.value]
        return "; ".join(parts + hits)


def _bridge_specificity(bridge: dict | None) -> tuple[float, str]:
    """How specific the named mechanism is.

    A bridge built from terms that appear across most of biology describes a
    research area; one naming particular regulators and a particular process
    describes a mechanism. Regulators count for more because they are the part
    an assay can be pointed at.
    """
    if not bridge:
        return 0.0, "no bridge"
    terms = bridge.get("terms") or []
    if not terms:
        return 0.0, "bridge has no terms"
    generic = [t for t in terms if t.casefold() in GENERIC_TERMS]
    regulators = [t for t in terms if t.isupper()]
    specific = [t for t in terms if t.casefold() not in GENERIC_TERMS and not t.isupper()]
    value = min(1.0, (len(specific) * 0.2) + (len(regulators) * 0.25))
    return round(value, 3), (
        f"{len(specific)} specific process term(s), {len(regulators)} named "
        f"regulator(s), {len(generic)} generic"
    )


def _evidence_directness(trace: dict) -> tuple[float, str]:
    """Share of supporting evidence that establishes a direct molecular link."""
    supporting = trace.get("supporting_evidence_ids") or []
    if not supporting:
        return 0.0, "no supporting evidence"
    bridge = trace.get("mechanistic_bridge") or {}
    direct = bridge.get("derived_from_evidence_ids") or []
    value = len(direct) / max(len(supporting), 1)
    return round(min(value, 1.0), 3), (
        f"{len(direct)} of {len(supporting)} supporting items establish a direct link"
    )


def _role_quality(bridge: dict | None) -> tuple[float, str]:
    """Share of bridge terms backed by a paper's own demonstrated finding."""
    if not bridge:
        return 0.0, "no bridge"
    provenance = bridge.get("term_provenance") or []
    if not provenance:
        return 0.5, "no per-term roles recorded; treated as neutral"
    primary = [p for p in provenance if p.get("finding_role") == "PRIMARY_EXPERIMENTAL_RESULT"]
    value = len(primary) / len(provenance)
    return round(value, 3), f"{len(primary)} of {len(provenance)} terms from primary findings"


def _corroboration(trace: dict) -> tuple[float, str]:
    """Independent sources. Deliberately WEAK: it is a tie-break, not a ranking.

    Capped low so that no amount of co-mention can outweigh a specific,
    directly-demonstrated mechanism. This is the component whose over-weighting
    caused the defect this module replaces.
    """
    supporting = trace.get("supporting_evidence_ids") or []
    value = min(len(supporting) / 6.0, 1.0)
    return round(value, 3), f"{len(supporting)} supporting source(s), weak factor only"


def _context_compatibility(trace: dict) -> tuple[float, str]:
    """Whether the diseases were compared in comparable biological context."""
    anchor = trace.get("molecular_anchor_present")
    stages = {item["stage"]: item for item in trace.get("stages", [])}
    cell = stages.get("CellTypeTissueComparison", {})
    assessable = cell.get("assessable", False)
    value = (0.6 if anchor else 0.0) + (0.4 if assessable else 0.0)
    return round(value, 3), (
        f"molecular anchor {'present' if anchor else 'absent'}, cell/tissue axis "
        f"{'comparable' if assessable else 'unassessed'}"
    )


def _variant_compatibility(trace: dict) -> tuple[float, str]:
    """Variant-effect compatibility where the question applies."""
    verdict = trace.get("variant_compatibility", "UNKNOWN")
    mapping = {"COMPATIBLE": 1.0, "PARTIALLY_COMPATIBLE": 0.6, "UNKNOWN": 0.5,
               "INCOMPATIBLE": 0.0}
    return mapping.get(verdict, 0.5), f"variant compatibility {verdict}"


def _tractability(trace: dict) -> tuple[float, str]:
    """Whether the open question could be settled by one comparative experiment."""
    bridge = trace.get("mechanistic_bridge") or {}
    terms = bridge.get("terms") or []
    regulators = [t for t in terms if t.isupper()]
    value = 1.0 if regulators else (0.5 if terms else 0.0)
    return round(value, 3), (
        "a named regulator gives an assay a target"
        if regulators
        else "no named regulator; the readout would be harder to define"
    )


def _contradiction_burden(trace: dict) -> tuple[float, str]:
    contradicting = trace.get("contradicting_evidence_ids") or []
    supporting = trace.get("supporting_evidence_ids") or []
    if not contradicting:
        return 0.0, "no contradicting evidence retrieved"
    value = min(len(contradicting) / max(len(supporting), 1), 1.0)
    return round(value, 3), f"{len(contradicting)} contradicting item(s)"


def _generic_overlap_penalty(trace: dict) -> tuple[float, str]:
    """Penalty where the retrieval feature is broad and the bridge did not improve on it."""
    bridge = trace.get("mechanistic_bridge") or {}
    terms = [t.casefold() for t in (bridge.get("terms") or [])]
    if not terms:
        return 1.0, "no bridge at all"
    generic = [t for t in terms if t in GENERIC_TERMS]
    value = len(generic) / len(terms)
    return round(value, 3), f"{len(generic)} of {len(terms)} bridge terms are generic"


WEIGHTS: dict[str, float] = {
    "mechanistic_specificity": 0.30,
    "evidence_directness": 0.22,
    "evidence_role_quality": 0.18,
    "context_compatibility": 0.12,
    "experimental_tractability": 0.10,
    "variant_compatibility": 0.05,
    # Weakest of all, by design. See _corroboration.
    "independent_corroboration": 0.03,
}
PENALTY_WEIGHTS: dict[str, float] = {
    "contradiction_burden": 0.20,
    "generic_overlap": 0.15,
}


def assess_candidate(
    trace: dict, relationship_class: str, *, independent: bool = True
) -> CandidateAssessment:
    """Score one candidate, or exclude it with a stated reason.

    Identity is checked before the relationship class, and separately from it. A
    pair can hold a perfectly good shared-mechanism relationship while not being
    two diseases at all -- which is exactly what the top-ranked candidates were.
    Ranking those highly would mean presenting one disease under two names as
    the system's best cross-disease discovery.
    """
    assessment = CandidateAssessment(
        disease_id=trace.get("disease_b_id", trace.get("pair_id", "")),
        disease_name=trace.get("disease_b", ""),
        relationship_class=relationship_class,
        eligible=True,
    )
    if not independent:
        assessment.eligible = False
        scoped = trace.get("scoped_identities") or []
        detail = (
            f" ({scoped[0]['scope']} -> {scoped[0]['relation']})" if scoped else ""
        )
        assessment.exclusion_reason = (
            "not an independent cross-disease pair: identity checking places "
            f"these labels within one entity{detail}"
        )
        return assessment
    if relationship_class in HARD_EXCLUSIONS:
        assessment.eligible = False
        assessment.exclusion_reason = HARD_EXCLUSIONS[relationship_class]
        return assessment

    bridge = trace.get("mechanistic_bridge")
    if not bridge:
        assessment.eligible = False
        assessment.exclusion_reason = (
            "no evidence-backed mechanistic bridge; there is nothing specific to test"
        )
        return assessment

    for name, (value, why) in {
        "mechanistic_specificity": _bridge_specificity(bridge),
        "evidence_directness": _evidence_directness(trace),
        "evidence_role_quality": _role_quality(bridge),
        "context_compatibility": _context_compatibility(trace),
        "experimental_tractability": _tractability(trace),
        "variant_compatibility": _variant_compatibility(trace),
        "independent_corroboration": _corroboration(trace),
    }.items():
        assessment.components.append(
            Component(name=name, value=value, weight=WEIGHTS[name], rationale=why)
        )
    for name, (value, why) in {
        "contradiction_burden": _contradiction_burden(trace),
        "generic_overlap": _generic_overlap_penalty(trace),
    }.items():
        assessment.penalties.append(
            Component(name=name, value=value, weight=PENALTY_WEIGHTS[name], rationale=why)
        )
    return assessment


def rank_candidates(
    traces: list[dict],
    classes: dict[str, str],
    independent: dict[str, bool] | None = None,
) -> list[CandidateAssessment]:
    """Assess every candidate and order the eligible ones."""
    independent = independent or {}
    assessments = [
        assess_candidate(
            trace,
            classes.get(trace.get("disease_b", ""), "UNKNOWN"),
            independent=independent.get(trace.get("disease_b", ""), True),
        )
        for trace in traces
    ]
    eligible = [item for item in assessments if item.eligible]
    eligible.sort(key=lambda item: (-item.total, item.disease_name))
    excluded = [item for item in assessments if not item.eligible]
    return eligible + excluded
