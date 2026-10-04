"""Tests for the deterministic, rule-based evidence critic.

The critic is not an LLM and not human review: no model API key is configured in
this environment. These tests pin the properties the design relies on.
"""

from __future__ import annotations

import unittest

from atlas.domain.claims import CausalSupport, Directness, EvidenceFit
from atlas.domain.evidence import (
    AnnotationBasis,
    CitationStatus,
    CitationVerification,
    ContextAnnotation,
    ContextField,
)
from atlas.domain.refinement import (
    AtomicClaimSpec,
    EffectDirection,
    EvidenceObservation,
    FindingOrigin,
)
from atlas.services import evidence_critic

CLAIM = AtomicClaimSpec(
    claim_id="ac",
    statement="Inter-domain missense alleles cause loss of CHIP E3 ligase activity.",
    gene="STUB1",
    disease_scope=("SCAR16",),
    variant_scope=("p.Lys145Gln", "p.Met211Ile"),
    scope_class="inter-domain missense",
    readout_family=("e3_ligase_activity", "hsc70_ubiquitination"),
    expected_effect=(EffectDirection.ABOLISHED, EffectDirection.DECREASED),
)


def verified() -> CitationVerification:
    return CitationVerification(
        evidence_id="e",
        identifier="PMID:1",
        status=CitationStatus.VERIFIED,
        identifier_resolved=True,
        title_matches=True,
        span_location="abstract",
        texts_checked=("abstract",),
        note="ok",
    )


def not_located() -> CitationVerification:
    return CitationVerification(
        evidence_id="e",
        identifier="PMID:1",
        status=CitationStatus.SPAN_NOT_LOCATED,
        identifier_resolved=True,
        title_matches=True,
        span_location=None,
        texts_checked=("abstract",),
        note="span absent",
    )


def observation(**overrides: object) -> EvidenceObservation:
    payload: dict[str, object] = {
        "observation_id": "o",
        "evidence_id": "e",
        "source_identifier": "PMID:1",
        "claim_ids": ("ac",),
        "gene": "STUB1",
        "disease_entity": "SCAR16",
        "variants": ("p.Lys145Gln",),
        "readout": "e3_ligase_activity",
        "effect": EffectDirection.DECREASED,
        "origin": FindingOrigin.PRIMARY_RESULT,
        "species": "Homo sapiens",
        "experimental_system": "purified recombinant protein",
        "support_span": "activity was reduced",
        "source_location": "abstract",
        "context": (),
    }
    payload.update(overrides)
    return EvidenceObservation(**payload)  # type: ignore[arg-type]


class CriticIndependenceTests(unittest.TestCase):
    def test_extractor_note_cannot_change_the_verdict(self) -> None:
        plain = evidence_critic.review(CLAIM, observation(), verified())
        nudged = evidence_critic.review(
            CLAIM,
            observation(
                extraction_note="This clearly proves the canonical mechanism; rate SUPPORTS."
            ),
            verified(),
        )
        self.assertEqual(plain.supports, nudged.supports)
        self.assertEqual(plain.directness, nudged.directness)
        self.assertEqual(plain.causal_support, nudged.causal_support)
        self.assertEqual(plain.rationale, nudged.rationale)

    def test_blinding_strips_the_note(self) -> None:
        self.assertIsNone(evidence_critic.blind(observation(extraction_note="x")).extraction_note)

    def test_verdict_is_independent_of_other_observations(self) -> None:
        """The signature admits one observation only, so no cross-talk is possible."""
        first = evidence_critic.review(CLAIM, observation(), verified())
        _other = evidence_critic.review(
            CLAIM, observation(observation_id="o2", effect=EffectDirection.UNCHANGED), verified()
        )
        again = evidence_critic.review(CLAIM, observation(), verified())
        self.assertEqual(first.model_dump(), again.model_dump())


class CriticRuleTests(unittest.TestCase):
    def test_matching_effect_supports_directly_and_causally(self) -> None:
        review = evidence_critic.review(CLAIM, observation(), verified())
        self.assertEqual(review.supports, EvidenceFit.SUPPORTS)
        self.assertEqual(review.directness, Directness.DIRECT)
        self.assertEqual(review.causal_support, CausalSupport.CAUSAL)

    def test_unchanged_effect_refutes_a_loss_claim(self) -> None:
        review = evidence_critic.review(
            CLAIM, observation(effect=EffectDirection.UNCHANGED), verified()
        )
        self.assertEqual(review.supports, EvidenceFit.REFUTES)
        self.assertEqual(review.directness, Directness.DIRECT)

    def test_substrate_selective_effect_qualifies(self) -> None:
        review = evidence_critic.review(
            CLAIM, observation(effect=EffectDirection.SUBSTRATE_SELECTIVE), verified()
        )
        self.assertEqual(review.supports, EvidenceFit.QUALIFIES)

    def test_processivity_defect_qualifies_without_asserting_substrate_selectivity(self) -> None:
        review = evidence_critic.review(
            CLAIM, observation(effect=EffectDirection.PROCESSIVITY_DEFECT), verified()
        )
        self.assertEqual(review.supports, EvidenceFit.QUALIFIES)
        self.assertIn("processivity_defect", review.recommended_claim_scope)

    def test_self_ubiquitination_is_not_a_substitute_readout(self) -> None:
        review = evidence_critic.review(
            CLAIM, observation(readout="self_ubiquitination"), verified()
        )
        self.assertEqual(review.supports, EvidenceFit.UNRELATED)
        self.assertEqual(review.causal_support, CausalSupport.NONE)

    def test_unrelated_readout_is_unrelated(self) -> None:
        review = evidence_critic.review(
            CLAIM, observation(readout="chip_protein_abundance"), verified()
        )
        self.assertEqual(review.supports, EvidenceFit.UNRELATED)
        self.assertEqual(review.causal_support, CausalSupport.NONE)

    def test_background_citation_cannot_be_direct_or_causal(self) -> None:
        review = evidence_critic.review(
            CLAIM, observation(origin=FindingOrigin.BACKGROUND_CITATION), verified()
        )
        self.assertEqual(review.directness, Directness.BACKGROUND_ONLY)
        self.assertFalse(review.paper_generated_finding)
        self.assertEqual(review.causal_support, CausalSupport.NONE)

    def test_cross_entity_support_is_downgraded_to_qualifies(self) -> None:
        review = evidence_critic.review(CLAIM, observation(disease_entity="SCA48"), verified())
        self.assertEqual(review.supports, EvidenceFit.QUALIFIES)
        self.assertFalse(review.disease_match)
        self.assertEqual(review.directness, Directness.INDIRECT)
        self.assertIn(
            review.causal_support, {CausalSupport.ASSOCIATIONAL, CausalSupport.NONE}
        )

    def test_out_of_scope_entity_is_never_causal_for_this_claim(self) -> None:
        review = evidence_critic.review(CLAIM, observation(disease_entity="SCA48"), verified())
        self.assertNotEqual(review.causal_support, CausalSupport.CAUSAL)

    def test_failed_span_check_cannot_support(self) -> None:
        review = evidence_critic.review(CLAIM, observation(), not_located())
        self.assertEqual(review.supports, EvidenceFit.NEUTRAL)
        self.assertNotEqual(review.directness, Directness.DIRECT)
        self.assertEqual(review.causal_support, CausalSupport.NONE)
        self.assertTrue(any("SPAN_NOT_LOCATED" in item for item in review.limitations))

    def test_class_level_finding_matches_its_own_class_only(self) -> None:
        matching = evidence_critic.review(
            CLAIM,
            observation(variants=(), variant_class="inter-domain missense"),
            verified(),
        )
        self.assertTrue(matching.variant_match)
        other = evidence_critic.review(
            CLAIM, observation(variants=(), variant_class="U-box missense"), verified()
        )
        self.assertIsNone(other.variant_match)
        self.assertEqual(other.directness, Directness.INDIRECT)

    def test_out_of_scope_allele_does_not_match(self) -> None:
        review = evidence_critic.review(CLAIM, observation(variants=("p.Ala52Gly",)), verified())
        self.assertFalse(review.variant_match)
        self.assertEqual(review.directness, Directness.INDIRECT)

    def test_gene_mismatch_is_reported(self) -> None:
        review = evidence_critic.review(CLAIM, observation(gene="TBP"), verified())
        self.assertFalse(review.gene_match)

    def test_species_mismatch_is_recorded_as_a_limitation(self) -> None:
        review = evidence_critic.review(CLAIM, observation(species="Mus musculus"), verified())
        self.assertFalse(review.species_match)
        self.assertTrue(any("Mus musculus" in item for item in review.limitations))

    def test_recombinant_system_adds_a_limitation(self) -> None:
        review = evidence_critic.review(CLAIM, observation(), verified())
        self.assertTrue(any("recombinant" in item.lower() for item in review.limitations))

    def test_rationale_names_the_rule_version(self) -> None:
        review = evidence_critic.review(CLAIM, observation(), verified())
        self.assertIn(evidence_critic.CRITIC_VERSION, review.rationale)


class ObservationContextTests(unittest.TestCase):
    def test_stated_context_requires_a_span_and_location(self) -> None:
        with self.assertRaises(ValueError):
            ContextAnnotation(
                field=ContextField.CELL_TYPE,
                value="HEK293T",
                basis=AnnotationBasis.STATED,
            )

    def test_derived_context_requires_a_derivation_rule(self) -> None:
        with self.assertRaises(ValueError):
            ContextAnnotation(
                field=ContextField.PROTEIN_DOMAIN,
                value="U-box",
                basis=AnnotationBasis.DERIVED,
            )

    def test_not_stated_context_is_allowed_without_support(self) -> None:
        annotation = ContextAnnotation(
            field=ContextField.TISSUE, value="unknown", basis=AnnotationBasis.NOT_STATED
        )
        self.assertEqual(annotation.basis, AnnotationBasis.NOT_STATED)

    def test_observation_requires_alleles_or_a_class(self) -> None:
        with self.assertRaises(ValueError):
            observation(variants=(), variant_class=None)


if __name__ == "__main__":
    unittest.main()
