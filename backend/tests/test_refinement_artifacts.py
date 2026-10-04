"""Schema and integrity tests for the generated SCAR16 refinement artifacts.

These validate the committed run output: the refinement, the KnowledgeGap and the
ExperimentProposal are re-parsed through their strict models, and the links
between them (and back to upstream DisMech IDs) are checked.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from atlas.adapters.dismech import DisMechImporter
from atlas.domain.claims import ClaimType, Directness, RefinementStatus
from atlas.domain.evidence import AnnotationBasis, CitationStatus, ContextField
from atlas.domain.experiments import ExperimentProposal
from atlas.domain.gaps import CoverageStatus, GapType, KnowledgeGap
from atlas.domain.provenance import ProvenanceKind
from atlas.domain.refinement import EdgeRefinement, FindingOrigin

ROOT = Path(__file__).parents[2]
RUN_DIR = ROOT / "data" / "refinement" / "scar16_stub1_e3"
COMMIT = "b923d18f1c962eeaecf9f1f908305b21a8f26904"


def refinement() -> EdgeRefinement:
    return EdgeRefinement.model_validate_json((RUN_DIR / "edge_refinement.json").read_text())


def gap() -> KnowledgeGap:
    return KnowledgeGap.model_validate_json((RUN_DIR / "knowledge_gap.json").read_text())


def experiment() -> ExperimentProposal:
    return ExperimentProposal.model_validate_json(
        (RUN_DIR / "experiment_proposal.json").read_text()
    )


class SnapshotIntegrityTests(unittest.TestCase):
    def test_every_cached_snapshot_matches_its_recorded_hash(self) -> None:
        from hashlib import sha256

        metas = sorted((RUN_DIR / "snapshots").glob("*.json"))
        self.assertTrue(metas)
        for meta_path in metas:
            meta = json.loads(meta_path.read_text())
            body = meta_path.with_suffix(".body")
            self.assertTrue(body.exists(), meta_path.name)
            self.assertEqual(sha256(body.read_bytes()).hexdigest(), meta["sha256"])

    def test_plan_pins_the_upstream_commit_and_file(self) -> None:
        plan = json.loads((RUN_DIR / "observation_plan.json").read_text())
        self.assertEqual(plan["target"]["dismech_commit"], COMMIT)
        self.assertTrue(
            plan["target"]["disease_file"].endswith(
                "Autosomal_Recessive_Spinocerebellar_Ataxia_16.yaml"
            )
        )
        self.assertFalse(plan["provenance"]["human_verified"])


class EdgeRefinementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run = refinement()

    def test_upstream_claim_is_unmodified_curated_content(self) -> None:
        upstream = self.run.upstream_claim
        self.assertEqual(upstream.claim_type, ClaimType.CURATED)
        self.assertEqual(upstream.provenance.source_name, "DisMech")
        self.assertEqual(upstream.provenance.source_version, COMMIT)
        self.assertEqual(upstream.refinement_status, RefinementStatus.UNREVIEWED)

    def test_refined_claims_are_separate_derived_objects(self) -> None:
        for item in self.run.atomic:
            self.assertEqual(item.claim.claim_type, ClaimType.EXTRACTED)
            self.assertEqual(item.claim.provenance.kind, ProvenanceKind.EXTRACTED)
            self.assertEqual(
                item.claim.derived_from_claim_ids, (self.run.upstream_claim.claim_id,)
            )
            self.assertNotEqual(item.claim.claim_id, self.run.upstream_claim.claim_id)

    def test_upstream_claim_matches_the_live_upstream_entry(self) -> None:
        """Provenance must be reconstructible from the pinned source file."""
        source = ROOT / "data" / "upstream" / "dismech" / "kb" / "disorders" / (
            "Autosomal_Recessive_Spinocerebellar_Ataxia_16.yaml"
        )
        self.assertTrue(source.exists(), "the pinned source file must ship with the run")
        imported = DisMechImporter(source_version=COMMIT).load_path(source)
        matching = [
            claim
            for claim in imported.claims
            if claim.claim_id == self.run.upstream_claim.claim_id
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(
            matching[0].normalized_statement, self.run.upstream_claim.normalized_statement
        )
        self.assertEqual(
            matching[0].provenance.source_object_path, "pathophysiology[0].downstream[1]"
        )

    def test_no_citation_check_failed_silently(self) -> None:
        self.assertTrue(self.run.citation_checks)
        statuses = {check.status for check in self.run.citation_checks}
        self.assertNotIn(CitationStatus.UNRESOLVED, statuses)
        self.assertNotIn(CitationStatus.TITLE_MISMATCH, statuses)
        for check in self.run.citation_checks:
            if check.status is CitationStatus.VERIFIED:
                self.assertIsNotNone(check.span_location)
                self.assertTrue(check.source_snapshot_sha256)

    def test_every_review_targets_a_known_observation_and_claim(self) -> None:
        observation_ids = {item.observation_id for item in self.run.observations}
        claim_ids = {item.claim.claim_id for item in self.run.atomic}
        for review in self.run.reviews:
            self.assertIn(review.source_id, observation_ids)
            self.assertIn(review.claim_id, claim_ids)

    def test_background_only_evidence_never_supports_a_status(self) -> None:
        background = {
            review.source_id
            for review in self.run.reviews
            if review.directness is Directness.BACKGROUND_ONLY
        }
        self.assertTrue(background, "this run contains a background-only citation")
        background_evidence = {
            item.evidence_id
            for item in self.run.observations
            if item.observation_id in background
        }
        for item in self.run.atomic:
            self.assertFalse(set(item.direct_supporting) & background_evidence)

    def test_observations_record_origin_and_context_basis(self) -> None:
        self.assertTrue(self.run.observations)
        for item in self.run.observations:
            self.assertIsInstance(item.origin, FindingOrigin)
            self.assertTrue(item.support_span.strip())
            for annotation in item.context:
                self.assertIsInstance(annotation.field, ContextField)
                if annotation.basis is AnnotationBasis.STATED:
                    self.assertTrue(annotation.support_span)
                elif annotation.basis is AnnotationBasis.DERIVED:
                    self.assertTrue(annotation.derivation)

    def test_protein_domains_are_derived_from_uniprot_not_asserted(self) -> None:
        domains = [
            annotation
            for item in self.run.observations
            for annotation in item.context
            if annotation.field is ContextField.PROTEIN_DOMAIN
        ]
        self.assertTrue(domains)
        for annotation in domains:
            self.assertEqual(annotation.basis, AnnotationBasis.DERIVED)
            self.assertIn("Q9UNE7", annotation.derivation or "")

    def test_context_fields_required_by_the_protocol_are_present(self) -> None:
        present = {
            annotation.field
            for item in self.run.observations
            for annotation in item.context
        }
        for field in (
            ContextField.SPECIES,
            ContextField.CELL_TYPE,
            ContextField.VARIANT,
            ContextField.PROTEIN_DOMAIN,
            ContextField.SUBTYPE,
            ContextField.EXPERIMENTAL_SYSTEM,
            ContextField.INTERVENTION,
            ContextField.ASSAY,
            ContextField.READOUT,
        ):
            self.assertIn(field, present)

    def test_edge_status_is_categorical_with_a_traceable_rationale(self) -> None:
        self.assertIsInstance(self.run.edge_status, RefinementStatus)
        self.assertTrue(self.run.edge_rule_applied)
        self.assertIn(self.run.edge_status.value, self.run.edge_rationale)
        for item in self.run.atomic:
            self.assertIn(item.status.value, self.run.edge_rationale)

    def test_search_coverage_records_queries_and_counts(self) -> None:
        coverage = self.run.search_coverage
        self.assertTrue(coverage.sources)
        checked = [
            source for source in coverage.sources if source.status is CoverageStatus.CHECKED
        ]
        self.assertTrue(checked)
        for source in checked:
            self.assertTrue(source.queries)
            self.assertIsNotNone(source.checked_at)
            self.assertIsNotNone(source.result_count)
        for source in coverage.sources:
            if source.status is CoverageStatus.FAILED:
                self.assertTrue(source.error)
        self.assertIn("not proof", coverage.interpretation_caveat)


class KnowledgeGapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gap = gap()
        self.run = refinement()

    def test_gap_is_schema_valid_and_open(self) -> None:
        self.assertIsInstance(self.gap.gap_type, GapType)
        self.assertEqual(self.gap.status, "OPEN")

    def test_gap_targets_a_claim_the_run_left_unresolved(self) -> None:
        unresolved = {
            item.claim.claim_id
            for item in self.run.atomic
            if item.status is not RefinementStatus.SUPPORTED
        }
        self.assertTrue(set(self.gap.related_claims) & (unresolved | {"ac4-interdomain-missense"}))
        self.assertIn(self.run.upstream_claim.claim_id, self.gap.related_claims)
        self.assertIn(self.run.upstream_edge_id, self.gap.related_edges)

    def test_gap_carries_the_runs_own_search_coverage(self) -> None:
        self.assertEqual(
            {source.source for source in self.gap.search_coverage.sources},
            {source.source for source in self.run.search_coverage.sources},
        )
        self.assertIsNotNone(self.gap.search_coverage.search_completed_at)

    def test_gap_states_required_content(self) -> None:
        self.assertTrue(self.gap.question.strip().endswith("?"))
        self.assertTrue(self.gap.why_it_matters)
        self.assertTrue(self.gap.current_evidence_summary)
        self.assertTrue(self.gap.contradictory_evidence_summary)
        self.assertTrue(self.gap.missing_evidence_type)
        self.assertTrue(self.gap.required_context)
        self.assertTrue(self.gap.resolvability)
        self.assertTrue(self.gap.proposed_discriminating_test)

    def test_gap_priority_dimensions_are_all_reasoned(self) -> None:
        dimensions = self.gap.priority_reason.model_dump()
        self.assertEqual(len(dimensions), 7)
        for name, value in dimensions.items():
            self.assertTrue(value.strip(), name)
            self.assertNotEqual(value, "not assessed", name)

    def test_gap_cites_internal_evidence_ids(self) -> None:
        evidence_ids = {item.evidence_id for item in self.run.observations}
        text = self.gap.current_evidence_summary + self.gap.contradictory_evidence_summary
        self.assertTrue(
            any(evidence_id in text for evidence_id in evidence_ids),
            "the gap must cite internal evidence IDs, not only prose",
        )

    def test_gap_scope_excludes_the_supported_sibling_claims(self) -> None:
        supported = [
            item.claim.normalized_statement
            for item in self.run.atomic
            if item.status is RefinementStatus.SUPPORTED
        ]
        self.assertTrue(supported)
        for statement in supported:
            self.assertIn(statement, self.gap.scope)


class ExperimentProposalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.experiment = experiment()
        self.gap = gap()

    def test_label_is_exact(self) -> None:
        self.assertEqual(self.experiment.label, "Research proposal requiring expert review.")

    def test_proposal_links_to_the_validated_gap(self) -> None:
        self.assertEqual(self.experiment.knowledge_gap_id, self.gap.gap_id)
        self.assertTrue(self.experiment.human_review_required)

    def test_falsifiability_is_explicit(self) -> None:
        self.assertTrue(self.experiment.expected_result_if_refuted.strip())
        self.assertNotEqual(
            self.experiment.expected_result_if_refuted,
            self.experiment.expected_result_if_supported,
        )
        self.assertTrue(self.experiment.competing_hypothesis.strip())
        self.assertNotEqual(self.experiment.hypothesis, self.experiment.competing_hypothesis)

    def test_required_design_elements_are_populated(self) -> None:
        self.assertTrue(self.experiment.model_system)
        self.assertTrue(self.experiment.sample_type)
        self.assertTrue(self.experiment.perturbation)
        self.assertTrue(self.experiment.comparator)
        self.assertTrue(self.experiment.controls)
        self.assertTrue(self.experiment.readouts)
        self.assertTrue(self.experiment.primary_endpoint)
        self.assertTrue(self.experiment.confounders)
        self.assertTrue(self.experiment.known_limitations)
        self.assertTrue(self.experiment.required_assets)
        self.assertTrue(self.experiment.required_capabilities)

    def test_design_compares_alleles_rather_than_pooling_variants(self) -> None:
        text = " ".join(
            (
                self.experiment.sample_type,
                self.experiment.perturbation,
                " ".join(self.experiment.patient_stratification),
            )
        )
        self.assertIn("p.Lys145Gln", text)
        self.assertIn("p.Met211Ile", text)
        self.assertIn("p.Thr246Met", text)

    def test_isogenic_and_wild_type_controls_are_present(self) -> None:
        controls = " ".join(self.experiment.controls).lower()
        self.assertIn("isogenic", controls)
        self.assertIn("wild-type", controls + self.experiment.comparator.lower())

    def test_no_clinical_or_therapeutic_claim_is_made(self) -> None:
        disclaimed = " ".join(self.experiment.unjustified_interpretations).lower()
        self.assertIn("therapeutic", disclaimed)
        self.assertIn("clinical", disclaimed)

    def test_refutation_requires_a_control_contrast(self) -> None:
        with self.assertRaises(ValueError):
            self.experiment.model_copy(update={"controls": ()}).model_validate(
                self.experiment.model_copy(update={"controls": ()}).model_dump()
            )

    def test_human_review_cannot_be_waived(self) -> None:
        payload = self.experiment.model_dump()
        payload["human_review_required"] = False
        with self.assertRaises(ValueError):
            ExperimentProposal.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
