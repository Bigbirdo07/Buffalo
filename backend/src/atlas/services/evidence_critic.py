"""Deterministic independent evidence critic.

The critic sees only one atomic claim's machine-readable scope, one extracted
observation, and that observation's citation check. It does not see other
observations, the extractor's notes, or any synthesis, so its verdict cannot be
anchored on the conclusion. Every verdict carries the rule trace that produced it.

A model-based critic can later replace ``review`` behind the same signature and
the same strict ``EvidenceReview`` schema.
"""

from __future__ import annotations

from atlas.domain.claims import CausalSupport, Directness, EvidenceFit, EvidenceReview
from atlas.domain.evidence import CitationStatus, CitationVerification
from atlas.domain.refinement import (
    AtomicClaimSpec,
    EffectDirection,
    EvidenceObservation,
    FindingOrigin,
)

LOSS_EFFECTS = frozenset({EffectDirection.ABOLISHED, EffectDirection.DECREASED})
PARTIAL_EFFECTS = frozenset(
    {
        EffectDirection.PROCESSIVITY_DEFECT,
        EffectDirection.SUBSTRATE_SELECTIVE,
        EffectDirection.PARTIALLY_RETAINED,
    }
)
CRITIC_VERSION = "deterministic-critic-v1"


def _fit(claim: AtomicClaimSpec, observation: EvidenceObservation) -> EvidenceFit:
    # A claim's own readout scope wins when declared, so an observation about a
    # different sub-step cannot be counted toward it even if a human assigned it.
    in_scope = claim.readout_scope or claim.readout_family
    if observation.readout not in in_scope:
        return EvidenceFit.UNRELATED
    expects_loss = bool(set(claim.expected_effect) & LOSS_EFFECTS)
    if observation.effect in claim.expected_effect:
        return EvidenceFit.SUPPORTS
    if observation.effect in PARTIAL_EFFECTS:
        return EvidenceFit.QUALIFIES
    retained = {EffectDirection.UNCHANGED, EffectDirection.INCREASED}
    if expects_loss and observation.effect in retained:
        return EvidenceFit.REFUTES
    return EvidenceFit.NEUTRAL


def blind(observation: EvidenceObservation) -> EvidenceObservation:
    """Strip free-text extractor reasoning before the critic sees an observation."""
    return observation.model_copy(update={"extraction_note": None})


def review(
    claim: AtomicClaimSpec,
    observation: EvidenceObservation,
    citation: CitationVerification,
) -> EvidenceReview:
    """Review one claim/observation pair. ``citation`` is the check of *this*
    observation's own support span against retrieved source text."""
    observation = blind(observation)
    trace: list[str] = []
    limitations: list[str] = []

    fit = _fit(claim, observation)
    trace.append(
        f"readout={observation.readout!r} effect={observation.effect.value} -> {fit.value}"
    )

    disease_match = observation.disease_entity in claim.disease_scope
    if not disease_match:
        trace.append(f"disease {observation.disease_entity!r} outside scope {claim.disease_scope}")
        limitations.append(
            f"Cross-entity evidence ({observation.disease_entity}); informative about the "
            "same protein but not a test in the claimed disease."
        )
        if fit in {EvidenceFit.SUPPORTS, EvidenceFit.REFUTES}:
            fit = EvidenceFit.QUALIFIES
            trace.append("cross-entity SUPPORTS/REFUTES downgraded to QUALIFIES")

    cell_type_match: bool | None = None
    if claim.cell_type_scope:
        if not observation.cell_types:
            cell_type_match = None
            limitations.append(
                "Observation does not state a cell type, so the claim's cell-type "
                "scope could not be checked."
            )
        else:
            cell_type_match = bool(
                {item.lower() for item in observation.cell_types}
                & {item.lower() for item in claim.cell_type_scope}
            )
            if not cell_type_match:
                trace.append(
                    f"cell type {observation.cell_types} outside scope "
                    f"{claim.cell_type_scope}"
                )
                limitations.append(
                    f"Measured in {', '.join(observation.cell_types)}, outside the "
                    "claim's cell-type scope; informative about the protein but not a "
                    "test in the claimed cell type."
                )
                if fit in {EvidenceFit.SUPPORTS, EvidenceFit.REFUTES}:
                    fit = EvidenceFit.QUALIFIES
                    trace.append("cross-cell-type SUPPORTS/REFUTES downgraded to QUALIFIES")

    named = set(observation.variants) & set(claim.variant_scope)
    class_level = not observation.variants and observation.variant_class == claim.scope_class
    variant_match: bool | None
    if named:
        variant_match = True
    elif class_level:
        variant_match = True
        trace.append(f"class-level finding for {claim.scope_class!r} (alleles not named in text)")
        limitations.append("Class-level statement; individual alleles not named in the text.")
    elif observation.variants:
        variant_match = False
    else:
        variant_match = None

    species_match = observation.species in claim.species_scope
    if not species_match:
        limitations.append(f"Species/system {observation.species!r} differs from the claim scope.")

    paper_generated = observation.origin is FindingOrigin.PRIMARY_RESULT
    citation_ok = citation.status is CitationStatus.VERIFIED
    attested = citation.status is CitationStatus.UPSTREAM_ATTESTED
    if attested:
        # The identifier resolves and a curator recorded the quotation, but the text
        # was not retrievable. Such evidence may qualify a claim -- it is real
        # curated observation -- but it may never on its own support or contradict
        # one, so a would-be SUPPORTS or REFUTES is capped at QUALIFIES.
        limitations.append(
            "Span not independently located: source text was not retrievable. "
            "Weight capped at QUALIFIES."
        )
        if fit in {EvidenceFit.SUPPORTS, EvidenceFit.REFUTES}:
            trace.append(f"citation UPSTREAM_ATTESTED -> {fit.value} capped to QUALIFIES")
            fit = EvidenceFit.QUALIFIES
    elif not citation_ok:
        limitations.append(f"Citation check: {citation.status.value} ({citation.note})")
        # A span absent from text we did retrieve, or an unresolvable reference,
        # cannot support or refute.
        fit = EvidenceFit.NEUTRAL
        paper_generated = False
        trace.append(f"span check {citation.status.value} -> NEUTRAL, cannot be DIRECT")

    if observation.origin is FindingOrigin.BACKGROUND_CITATION:
        directness = Directness.BACKGROUND_ONLY
        paper_generated = False
        trace.append("text attributes the finding to earlier work -> BACKGROUND_ONLY")
    elif (
        (citation_ok or attested)
        and paper_generated
        and disease_match
        and variant_match is True
        and cell_type_match is not False
        and fit is not EvidenceFit.UNRELATED
    ):
        directness = Directness.DIRECT
        trace.append("paper-generated, in-disease, in-scope allele/class, readout -> DIRECT")
    else:
        directness = Directness.INDIRECT
        trace.append("not all DIRECT conditions met -> INDIRECT")

    if "recombinant" in observation.experimental_system.lower():
        limitations.append("Purified recombinant protein; cellular abundance and context absent.")
    if "overexpress" in observation.experimental_system.lower():
        limitations.append("Overexpression system; endogenous dosage and cell type not modeled.")

    if directness is Directness.BACKGROUND_ONLY or fit in {
        EvidenceFit.NEUTRAL,
        EvidenceFit.UNRELATED,
    }:
        causal = CausalSupport.NONE
    elif (
        paper_generated
        and observation.variants
        and disease_match
        and variant_match is True
        and cell_type_match is not False
        and not attested
    ):
        # An in-scope allele was introduced and the readout measured: interventional
        # design for *this* claim. Out-of-scope entities/alleles can be at most
        # associational for the claim under review, however clean their own design,
        # and so can evidence whose span we could not read for ourselves.
        causal = CausalSupport.CAUSAL
    else:
        causal = CausalSupport.ASSOCIATIONAL

    alleles = ", ".join(observation.variants) or observation.variant_class or "unspecified"
    scope = (
        f"{alleles}: {observation.readout} {observation.effect.value} "
        f"({observation.experimental_system}; {observation.disease_entity})"
    )
    return EvidenceReview(
        claim_id=claim.claim_id,
        source_id=observation.observation_id,
        supports=fit,
        directness=directness,
        paper_generated_finding=paper_generated,
        disease_match=disease_match,
        gene_match=observation.gene == claim.gene,
        direction_match=fit is EvidenceFit.SUPPORTS,
        species_match=species_match,
        cell_type_match=cell_type_match,
        variant_match=variant_match,
        causal_support=causal,
        recommended_claim_scope=scope,
        limitations=tuple(dict.fromkeys(limitations)),
        rationale=f"[{CRITIC_VERSION}] " + "; ".join(trace),
    )
