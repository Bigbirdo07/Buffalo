from __future__ import annotations

import unittest
from datetime import date

from pydantic import ValidationError

from atlas.domain.claims import CausalSupport, Directness, EvidenceFit, EvidenceReview
from atlas.domain.evidence import (
    EvidenceItem,
    EvidenceModality,
    EvidenceOrigin,
    EvidenceRelation,
    StudyDesign,
)
from atlas.domain.provenance import Provenance, ProvenanceKind


def provenance() -> Provenance:
    return Provenance(
        kind=ProvenanceKind.EXTRACTED,
        source_name="test",
        source_version="1",
        source_object_path="fixture",
        source_snapshot_sha256="a" * 64,
        extraction_method="fixture",
    )


class ScientificFixtureTests(unittest.TestCase):
    def test_case_a_primary_result_can_support_scoped_claim(self) -> None:
        review = EvidenceReview(
            claim_id="c1",
            source_id="e1",
            supports=EvidenceFit.SUPPORTS,
            directness=Directness.DIRECT,
            paper_generated_finding=True,
            disease_match=True,
            gene_match=True,
            direction_match=True,
            species_match=True,
            causal_support=CausalSupport.CAUSAL,
            recommended_claim_scope="GENE1 loss reduces Complex Y activity in the tested neurons.",
            limitations=("Single cell model",),
            rationale="The perturbation and rescue directly test the scoped edge.",
        )
        self.assertEqual(review.supports, EvidenceFit.SUPPORTS)

    def test_case_b_wrong_disease_cannot_be_support(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceReview(
                claim_id="c1",
                source_id="e2",
                supports=EvidenceFit.SUPPORTS,
                directness=Directness.DIRECT,
                paper_generated_finding=True,
                disease_match=False,
                species_match=True,
                causal_support=CausalSupport.ASSOCIATIONAL,
                recommended_claim_scope="Other disease only",
                limitations=("Wrong disease",),
                rationale="The source does not study the target disease.",
            )

    def test_case_c_introduction_is_not_paper_generated_result(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceReview(
                claim_id="c1",
                source_id="e3",
                supports=EvidenceFit.QUALIFIES,
                directness=Directness.BACKGROUND_ONLY,
                paper_generated_finding=True,
                disease_match=True,
                species_match=True,
                causal_support=CausalSupport.NONE,
                recommended_claim_scope="Background assertion only",
                limitations=("Introduction passage",),
                rationale="The sentence cites previous work.",
            )

    def test_case_d_mouse_result_keeps_model_organism_modality(self) -> None:
        item = EvidenceItem(
            evidence_id="e4",
            claim_id="c1",
            pmid="PMID:12345",
            exact_supported_span="Knockout mice showed the phenotype.",
            evidence_relation=EvidenceRelation.SUPPORTS,
            evidence_origin=EvidenceOrigin.PRIMARY_RESULT,
            evidence_modality=EvidenceModality.MODEL_ORGANISM,
            study_design=StudyDesign.EXPERIMENTAL_MODEL,
            species=("Mus musculus",),
            limitations=("Cross-species support; does not prove a human mechanism.",),
            retrieval_date=date(2026, 10, 3),
            provenance=provenance(),
        )
        self.assertNotIn("Homo sapiens", item.species)

    def test_case_e_fibroblast_context_is_explicit(self) -> None:
        item = EvidenceItem(
            evidence_id="e5",
            claim_id="c1",
            doi="https://doi.org/10.1000/fixture",
            exact_supported_span="The effect was observed in fibroblasts.",
            evidence_relation=EvidenceRelation.QUALIFIES,
            evidence_origin=EvidenceOrigin.PRIMARY_RESULT,
            evidence_modality=EvidenceModality.HUMAN_PATIENT_DERIVED,
            study_design=StudyDesign.CELL_EXPERIMENT,
            species=("Homo sapiens",),
            cell_type=("fibroblast",),
            limitations=("Neuronal context was not tested.",),
            retrieval_date=date(2026, 10, 3),
            provenance=provenance(),
        )
        self.assertEqual(item.cell_type, ("fibroblast",))

    def test_case_g_support_and_refutation_remain_distinct(self) -> None:
        base = dict(
            claim_id="c1",
            exact_supported_span="Result",
            evidence_origin=EvidenceOrigin.PRIMARY_RESULT,
            evidence_modality=EvidenceModality.IN_VITRO,
            retrieval_date=date(2026, 10, 3),
            provenance=provenance(),
        )
        support = EvidenceItem(
            evidence_id="support", pmid="1", evidence_relation=EvidenceRelation.SUPPORTS, **base
        )
        refute = EvidenceItem(
            evidence_id="refute", pmid="2", evidence_relation=EvidenceRelation.REFUTES, **base
        )
        self.assertNotEqual(support.evidence_relation, refute.evidence_relation)

    def test_malformed_citation_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceItem(
                evidence_id="bad",
                claim_id="c1",
                pmid="not-a-pmid",
                exact_supported_span="text",
                evidence_relation=EvidenceRelation.NEUTRAL,
                evidence_origin=EvidenceOrigin.DATABASE_ASSERTION,
                evidence_modality=EvidenceModality.OTHER,
                retrieval_date=date(2026, 10, 3),
                provenance=provenance(),
            )


if __name__ == "__main__":
    unittest.main()

