"""Pure synthesis of an edge refinement from reviewed observations.

The rules are categorical and written down here so a status is always
reproducible from its inputs. There is no numeric confidence score.

Atomic-claim rules (first match wins):

* A1 no DIRECT review -> INSUFFICIENT_EVIDENCE
* A2 DIRECT support only -> SUPPORTED
* A3 DIRECT support and DIRECT refutation/qualification -> CONTEXT_DEPENDENT
* A4 no DIRECT support, DIRECT refutation from >= 2 independent publications and no
  DIRECT qualification -> CONTRADICTED
* A5 no DIRECT support, DIRECT refutation and DIRECT qualification -> CONTEXT_DEPENDENT
  (direct evidence shows an effect that is real but not the one claimed: it varies by
  allele, substrate or assay condition within the claim's own scope)
* A6 no DIRECT support, DIRECT refutation from 1 publication only -> INSUFFICIENT_EVIDENCE
* A7 DIRECT qualification only -> PARTIALLY_SUPPORTED

A5 exists because INSUFFICIENT_EVIDENCE must mean "not enough direct evidence to
judge". A claim with direct refutation *and* direct qualification has ample direct
evidence; what it lacks is uniformity across its scope. Folding that case into
INSUFFICIENT_EVIDENCE would hide characterized heterogeneity behind a word that
means ignorance.

Edge rules over its atomic claims:

* E1 every atomic claim SUPPORTED -> SUPPORTED
* E2 at least one SUPPORTED and at least one CONTRADICTED, CONTEXT_DEPENDENT or
  PARTIALLY_SUPPORTED -> CONTEXT_DEPENDENT (the edge holds for some contexts only)
* E3 at least one SUPPORTED, the rest INSUFFICIENT_EVIDENCE -> PARTIALLY_SUPPORTED
* E4 none SUPPORTED, at least one CONTRADICTED -> CONTRADICTED
* E5 otherwise -> INSUFFICIENT_EVIDENCE
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from atlas.domain.claims import (
    Claim,
    ClaimType,
    Directness,
    EvidenceFit,
    EvidenceReview,
    RefinementStatus,
)
from atlas.domain.provenance import Provenance, ProvenanceKind
from atlas.domain.refinement import (
    AtomicClaimSpec,
    AtomicClaimSynthesis,
    EvidenceObservation,
)

SYNTHESIS_VERSION = "categorical-synthesis-v1"


def _ids(
    reviews: Sequence[EvidenceReview], by_obs: dict[str, EvidenceObservation]
) -> tuple[str, ...]:
    """Observation-precise references, as ``<evidence_id>#<observation_id>``.

    One publication can yield several distinct findings (a primary result and a
    background citation, say), which share a single upstream evidence_id. Citing
    the evidence_id alone would not say which finding set the status, so the
    observation id is carried with it.
    """
    return tuple(
        dict.fromkeys(
            f"{by_obs[review.source_id].evidence_id}#{review.source_id}" for review in reviews
        )
    )


def _evidence_ids(
    reviews: Sequence[EvidenceReview], by_obs: dict[str, EvidenceObservation]
) -> tuple[str, ...]:
    return tuple(dict.fromkeys(by_obs[review.source_id].evidence_id for review in reviews))


def synthesize_claim(
    spec: AtomicClaimSpec,
    reviews: Sequence[EvidenceReview],
    observations: Sequence[EvidenceObservation],
    *,
    upstream: Claim,
    provenance: Provenance,
) -> AtomicClaimSynthesis:
    by_obs = {item.observation_id: item for item in observations}
    own = [review for review in reviews if review.claim_id == spec.claim_id]
    direct = [review for review in own if review.directness is Directness.DIRECT]
    ds = [review for review in direct if review.supports is EvidenceFit.SUPPORTS]
    dr = [review for review in direct if review.supports is EvidenceFit.REFUTES]
    dq = [review for review in direct if review.supports is EvidenceFit.QUALIFIES]
    indirect = [review for review in own if review.directness is Directness.INDIRECT]
    background = [review for review in own if review.directness is Directness.BACKGROUND_ONLY]
    refuting_sources = _ids(dr, by_obs)
    independent_refuting = {by_obs[review.source_id].source_identifier for review in dr}

    if not direct:
        status, rule = RefinementStatus.INSUFFICIENT_EVIDENCE, "A1"
    elif ds and not (dr or dq):
        status, rule = RefinementStatus.SUPPORTED, "A2"
    elif ds:
        status, rule = RefinementStatus.CONTEXT_DEPENDENT, "A3"
    elif dr and not dq and len(independent_refuting) >= 2:
        status, rule = RefinementStatus.CONTRADICTED, "A4"
    elif dr and dq:
        status, rule = RefinementStatus.CONTEXT_DEPENDENT, "A5"
    elif dr:
        status, rule = RefinementStatus.INSUFFICIENT_EVIDENCE, "A6"
    else:
        status, rule = RefinementStatus.PARTIALLY_SUPPORTED, "A7"

    def describe(label: str, items: Sequence[EvidenceReview]) -> str:
        if not items:
            return f"{label}: none"
        parts = [
            f"{by_obs[r.source_id].evidence_id}#{r.source_id} ({r.recommended_claim_scope})"
            for r in items
        ]
        return f"{label}: " + "; ".join(parts)

    rationale = " | ".join(
        (
            f"[{SYNTHESIS_VERSION} rule {rule}] {status.value}",
            describe("direct support", ds),
            describe("direct refutation", dr),
            describe("direct qualification", dq),
            describe("indirect (does not set status)", indirect),
            describe("background only (does not set status)", background),
        )
    )
    cited = tuple(
        dict.fromkeys(
            (
                *_evidence_ids(direct, by_obs),
                *_evidence_ids(indirect, by_obs),
                *_evidence_ids(background, by_obs),
            )
        )
    )
    claim = Claim(
        claim_id=spec.claim_id,
        subject=upstream.subject,
        predicate=upstream.predicate,
        object=upstream.object,
        normalized_statement=spec.statement,
        original_statement=upstream.original_statement,
        claim_scope=f"Atomic decomposition, allele class: {spec.scope_class}",
        claim_type=ClaimType.EXTRACTED,
        disease_context=upstream.disease_context,
        variant_context=spec.variant_scope,
        protein_domain_context=(spec.scope_class,),
        species=spec.species_scope,
        source_claim_origin=upstream.source_claim_origin,
        extraction_method="structured_decomposition_v1",
        derived_from_claim_ids=(upstream.claim_id,),
        last_reviewed_at=datetime.now(UTC),
        refinement_status=status if cited else RefinementStatus.UNREVIEWED,
        status_rationale=rationale if cited else None,
        rationale_evidence_ids=cited,
        provenance=provenance,
    )
    return AtomicClaimSynthesis(
        claim=claim,
        status=status,
        direct_supporting=_ids(ds, by_obs),
        direct_refuting=refuting_sources,
        direct_qualifying=_ids(dq, by_obs),
        indirect=_ids(indirect, by_obs),
        background_only=_ids(background, by_obs),
        rule_applied=rule,
        rationale=rationale,
    )


def synthesize_edge(atomic: Sequence[AtomicClaimSynthesis]) -> tuple[RefinementStatus, str, str]:
    statuses = [item.status for item in atomic]
    supported = [item for item in atomic if item.status is RefinementStatus.SUPPORTED]
    divergent = {
        RefinementStatus.CONTRADICTED,
        RefinementStatus.CONTEXT_DEPENDENT,
        RefinementStatus.PARTIALLY_SUPPORTED,
    }
    if supported and len(supported) == len(atomic):
        status, rule = RefinementStatus.SUPPORTED, "E1"
    elif supported and divergent & set(statuses):
        status, rule = RefinementStatus.CONTEXT_DEPENDENT, "E2"
    elif supported:
        status, rule = RefinementStatus.PARTIALLY_SUPPORTED, "E3"
    elif RefinementStatus.CONTRADICTED in statuses:
        status, rule = RefinementStatus.CONTRADICTED, "E4"
    else:
        status, rule = RefinementStatus.INSUFFICIENT_EVIDENCE, "E5"
    summary = "; ".join(
        f"{item.claim.normalized_statement} -> {item.status.value} (rule {item.rule_applied}; "
        f"evidence {', '.join(item.claim.rationale_evidence_ids) or 'none'})"
        for item in atomic
    )
    return status, rule, f"[{SYNTHESIS_VERSION} rule {rule}] {status.value}: {summary}"


def derived_provenance(
    upstream: Provenance, *, method: str, payload: dict[str, object] | None = None
) -> Provenance:
    return Provenance(
        kind=ProvenanceKind.EXTRACTED,
        source_name="atlas-refinement",
        source_version=upstream.source_version,
        source_object_path=upstream.source_object_path,
        source_snapshot_sha256=upstream.source_snapshot_sha256,
        extraction_method=method,
        source_payload=dict(payload or {}),
    )
