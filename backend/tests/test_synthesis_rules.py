"""Tests pinning every categorical synthesis rule (A1-A7, E1-E5)."""

from __future__ import annotations

import unittest

from atlas.domain.claims import (
    CausalSupport,
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
    EffectDirection,
    EvidenceObservation,
    FindingOrigin,
)
from atlas.services.refinement import (
    derived_provenance,
    synthesize_claim,
    synthesize_edge,
)

SPEC = AtomicClaimSpec(
    claim_id="ac",
    statement="Alleles cause loss of activity.",
    gene="STUB1",
    disease_scope=("SCAR16",),
    variant_scope=("p.Lys145Gln",),
    scope_class="inter-domain missense",
    readout_family=("e3_ligase_activity",),
    expected_effect=(EffectDirection.ABOLISHED, EffectDirection.DECREASED),
)


def upstream_provenance() -> Provenance:
    return Provenance(
        kind=ProvenanceKind.CURATED,
        source_name="DisMech",
        source_version="commit",
        source_object_path="pathophysiology[0].downstream[1]",
        source_snapshot_sha256="a" * 64,
        extraction_method="deterministic_dismech_adapter_v2",
    )


def upstream_claim() -> Claim:
    return Claim(
        claim_id="upstream",
        subject="s",
        predicate="CAUSES_OR_CONTRIBUTES_TO",
        object="o",
        normalized_statement="s contributes to o.",
        original_statement="original upstream wording",
        claim_scope="Imported explicit DisMech downstream edge",
        claim_type=ClaimType.CURATED,
        disease_context="disease",
        source_claim_origin="pathophysiology[0].downstream[1]",
        extraction_method="deterministic_dismech_edge_import",
        provenance=upstream_provenance(),
    )


def observation(obs_id: str, evidence_id: str, pmid: str) -> EvidenceObservation:
    return EvidenceObservation(
        observation_id=obs_id,
        evidence_id=evidence_id,
        source_identifier=pmid,
        claim_ids=("ac",),
        gene="STUB1",
        disease_entity="SCAR16",
        variants=("p.Lys145Gln",),
        readout="e3_ligase_activity",
        effect=EffectDirection.DECREASED,
        origin=FindingOrigin.PRIMARY_RESULT,
        species="Homo sapiens",
        experimental_system="cells",
        support_span="span",
        source_location="abstract",
        context=(),
    )


def review(
    obs_id: str,
    fit: EvidenceFit,
    directness: Directness,
) -> EvidenceReview:
    causal = (
        CausalSupport.CAUSAL
        if fit in {EvidenceFit.SUPPORTS, EvidenceFit.REFUTES, EvidenceFit.QUALIFIES}
        and directness is Directness.DIRECT
        else CausalSupport.NONE
    )
    return EvidenceReview(
        claim_id="ac",
        source_id=obs_id,
        supports=fit,
        directness=directness,
        paper_generated_finding=directness is not Directness.BACKGROUND_ONLY,
        disease_match=True,
        species_match=True,
        causal_support=causal,
        recommended_claim_scope=f"{obs_id} scope",
        limitations=(),
        rationale="test",
    )


def synthesize(pairs: list[tuple[str, EvidenceFit, Directness, str]]) -> AtomicClaimSynthesis:
    observations = [
        observation(obs_id, f"ev-{obs_id}", pmid) for obs_id, _, _, pmid in pairs
    ]
    reviews = [review(obs_id, fit, directness) for obs_id, fit, directness, _ in pairs]
    return synthesize_claim(
        SPEC,
        reviews,
        observations,
        upstream=upstream_claim(),
        provenance=derived_provenance(upstream_provenance(), method="structured_decomposition_v1"),
    )


class AtomicRuleTests(unittest.TestCase):
    def test_a1_no_direct_review_is_insufficient(self) -> None:
        result = synthesize([("o1", EvidenceFit.SUPPORTS, Directness.INDIRECT, "PMID:1")])
        self.assertEqual(result.status, RefinementStatus.INSUFFICIENT_EVIDENCE)
        self.assertEqual(result.rule_applied, "A1")

    def test_a1_applies_when_only_background_exists(self) -> None:
        result = synthesize([("o1", EvidenceFit.SUPPORTS, Directness.BACKGROUND_ONLY, "PMID:1")])
        self.assertEqual(result.rule_applied, "A1")
        self.assertEqual(result.background_only, ("ev-o1#o1",))
        self.assertEqual(result.direct_supporting, ())

    def test_a2_direct_support_only_is_supported(self) -> None:
        result = synthesize([("o1", EvidenceFit.SUPPORTS, Directness.DIRECT, "PMID:1")])
        self.assertEqual(result.status, RefinementStatus.SUPPORTED)
        self.assertEqual(result.rule_applied, "A2")

    def test_a3_support_plus_refutation_is_context_dependent(self) -> None:
        result = synthesize(
            [
                ("o1", EvidenceFit.SUPPORTS, Directness.DIRECT, "PMID:1"),
                ("o2", EvidenceFit.REFUTES, Directness.DIRECT, "PMID:2"),
            ]
        )
        self.assertEqual(result.status, RefinementStatus.CONTEXT_DEPENDENT)
        self.assertEqual(result.rule_applied, "A3")

    def test_a4_two_independent_refutations_contradict(self) -> None:
        result = synthesize(
            [
                ("o1", EvidenceFit.REFUTES, Directness.DIRECT, "PMID:1"),
                ("o2", EvidenceFit.REFUTES, Directness.DIRECT, "PMID:2"),
            ]
        )
        self.assertEqual(result.status, RefinementStatus.CONTRADICTED)
        self.assertEqual(result.rule_applied, "A4")

    def test_two_refutations_from_one_publication_do_not_contradict(self) -> None:
        result = synthesize(
            [
                ("o1", EvidenceFit.REFUTES, Directness.DIRECT, "PMID:1"),
                ("o2", EvidenceFit.REFUTES, Directness.DIRECT, "PMID:1"),
            ]
        )
        self.assertEqual(result.status, RefinementStatus.INSUFFICIENT_EVIDENCE)
        self.assertEqual(result.rule_applied, "A6")

    def test_a5_refutation_with_qualification_is_context_dependent(self) -> None:
        result = synthesize(
            [
                ("o1", EvidenceFit.REFUTES, Directness.DIRECT, "PMID:1"),
                ("o2", EvidenceFit.QUALIFIES, Directness.DIRECT, "PMID:2"),
                ("o3", EvidenceFit.REFUTES, Directness.DIRECT, "PMID:3"),
            ]
        )
        self.assertEqual(result.status, RefinementStatus.CONTEXT_DEPENDENT)
        self.assertEqual(result.rule_applied, "A5")

    def test_a6_single_refutation_is_insufficient_not_contradicted(self) -> None:
        result = synthesize([("o1", EvidenceFit.REFUTES, Directness.DIRECT, "PMID:1")])
        self.assertEqual(result.status, RefinementStatus.INSUFFICIENT_EVIDENCE)
        self.assertEqual(result.rule_applied, "A6")

    def test_a7_qualification_only_is_partially_supported(self) -> None:
        result = synthesize([("o1", EvidenceFit.QUALIFIES, Directness.DIRECT, "PMID:1")])
        self.assertEqual(result.status, RefinementStatus.PARTIALLY_SUPPORTED)
        self.assertEqual(result.rule_applied, "A7")


class SynthesisTraceTests(unittest.TestCase):
    def test_rationale_cites_internal_evidence_ids(self) -> None:
        result = synthesize(
            [
                ("o1", EvidenceFit.SUPPORTS, Directness.DIRECT, "PMID:1"),
                ("o2", EvidenceFit.REFUTES, Directness.DIRECT, "PMID:2"),
            ]
        )
        self.assertIn("ev-o1#o1", result.rationale)
        self.assertIn("ev-o2#o2", result.rationale)
        self.assertEqual(result.claim.rationale_evidence_ids, ("ev-o1", "ev-o2"))
        self.assertIn("rule A3", result.rationale)

    def test_rationale_contains_no_numeric_confidence(self) -> None:
        result = synthesize([("o1", EvidenceFit.SUPPORTS, Directness.DIRECT, "PMID:1")])
        self.assertNotIn("confidence", result.rationale.lower())
        self.assertFalse(hasattr(result, "score"))
        self.assertFalse(hasattr(result, "confidence"))

    def test_indirect_and_background_are_listed_but_do_not_set_status(self) -> None:
        result = synthesize(
            [
                ("o1", EvidenceFit.SUPPORTS, Directness.DIRECT, "PMID:1"),
                ("o2", EvidenceFit.SUPPORTS, Directness.INDIRECT, "PMID:2"),
                ("o3", EvidenceFit.SUPPORTS, Directness.BACKGROUND_ONLY, "PMID:3"),
            ]
        )
        self.assertEqual(result.status, RefinementStatus.SUPPORTED)
        self.assertEqual(result.indirect, ("ev-o2#o2",))
        self.assertEqual(result.background_only, ("ev-o3#o3",))
        self.assertIn("does not set status", result.rationale)

    def test_refined_claim_is_derived_not_curated(self) -> None:
        result = synthesize([("o1", EvidenceFit.SUPPORTS, Directness.DIRECT, "PMID:1")])
        self.assertEqual(result.claim.claim_type, ClaimType.EXTRACTED)
        self.assertEqual(result.claim.provenance.kind, ProvenanceKind.EXTRACTED)
        self.assertEqual(result.claim.derived_from_claim_ids, ("upstream",))
        self.assertEqual(result.claim.original_statement, "original upstream wording")
        self.assertEqual(result.claim.normalized_statement, SPEC.statement)
        self.assertEqual(result.claim.provenance.source_name, "atlas-refinement")

    def test_reviewed_claim_requires_rationale_and_ids(self) -> None:
        result = synthesize([("o1", EvidenceFit.SUPPORTS, Directness.DIRECT, "PMID:1")])
        self.assertTrue(result.claim.status_rationale)
        self.assertTrue(result.claim.rationale_evidence_ids)
        self.assertIsNotNone(result.claim.last_reviewed_at)

    def test_claim_with_no_evidence_stays_unreviewed(self) -> None:
        result = synthesize([])
        self.assertEqual(result.claim.refinement_status, RefinementStatus.UNREVIEWED)
        self.assertIsNone(result.claim.status_rationale)

    def test_reviews_for_other_claims_are_ignored(self) -> None:
        observations = [observation("o1", "ev-o1", "PMID:1")]
        foreign = review("o1", EvidenceFit.SUPPORTS, Directness.DIRECT).model_copy(
            update={"claim_id": "other"}
        )
        result = synthesize_claim(
            SPEC,
            [foreign],
            observations,
            upstream=upstream_claim(),
            provenance=derived_provenance(
                upstream_provenance(), method="structured_decomposition_v1"
            ),
        )
        self.assertEqual(result.rule_applied, "A1")


def atomic(status: RefinementStatus, name: str) -> AtomicClaimSynthesis:
    pairs = {
        RefinementStatus.SUPPORTED: (EvidenceFit.SUPPORTS, Directness.DIRECT),
        RefinementStatus.PARTIALLY_SUPPORTED: (EvidenceFit.QUALIFIES, Directness.DIRECT),
        RefinementStatus.INSUFFICIENT_EVIDENCE: (EvidenceFit.SUPPORTS, Directness.INDIRECT),
    }
    fit, directness = pairs.get(status, (EvidenceFit.SUPPORTS, Directness.DIRECT))
    result = synthesize([(name, fit, directness, f"PMID:{name}")])
    return result.model_copy(update={"status": status})


class EdgeRuleTests(unittest.TestCase):
    def test_e1_all_supported(self) -> None:
        status, rule, _ = synthesize_edge(
            [atomic(RefinementStatus.SUPPORTED, "a"), atomic(RefinementStatus.SUPPORTED, "b")]
        )
        self.assertEqual((status, rule), (RefinementStatus.SUPPORTED, "E1"))

    def test_e2_mixed_support_and_divergence(self) -> None:
        status, rule, _ = synthesize_edge(
            [
                atomic(RefinementStatus.SUPPORTED, "a"),
                atomic(RefinementStatus.CONTEXT_DEPENDENT, "b"),
            ]
        )
        self.assertEqual((status, rule), (RefinementStatus.CONTEXT_DEPENDENT, "E2"))

    def test_e3_support_with_only_insufficient_siblings(self) -> None:
        status, rule, _ = synthesize_edge(
            [
                atomic(RefinementStatus.SUPPORTED, "a"),
                atomic(RefinementStatus.INSUFFICIENT_EVIDENCE, "b"),
            ]
        )
        self.assertEqual((status, rule), (RefinementStatus.PARTIALLY_SUPPORTED, "E3"))

    def test_e4_no_support_with_contradiction(self) -> None:
        status, rule, _ = synthesize_edge(
            [
                atomic(RefinementStatus.CONTRADICTED, "a"),
                atomic(RefinementStatus.INSUFFICIENT_EVIDENCE, "b"),
            ]
        )
        self.assertEqual((status, rule), (RefinementStatus.CONTRADICTED, "E4"))

    def test_e5_otherwise_insufficient(self) -> None:
        status, rule, _ = synthesize_edge([atomic(RefinementStatus.INSUFFICIENT_EVIDENCE, "a")])
        self.assertEqual((status, rule), (RefinementStatus.INSUFFICIENT_EVIDENCE, "E5"))

    def test_edge_rationale_lists_every_atomic_claim(self) -> None:
        _, _, rationale = synthesize_edge(
            [
                atomic(RefinementStatus.SUPPORTED, "a"),
                atomic(RefinementStatus.CONTEXT_DEPENDENT, "b"),
            ]
        )
        self.assertIn("ev-a", rationale)
        self.assertIn("ev-b", rationale)
        self.assertIn("rule", rationale)


if __name__ == "__main__":
    unittest.main()
