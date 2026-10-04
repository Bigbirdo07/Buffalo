"""Tests for the corpus claim-fit detectors.

Each detector is pinned on a synthetic document so its semantics are explicit,
and the negative cases matter as much as the positive ones: a flag list is only
useful if it stays quiet on ordinary curation.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from atlas.services.claim_fit_audit import Severity, audit_document, detectors

ROOT = Path(__file__).parents[2]
AUDIT = ROOT / "data" / "audit" / "claim_fit.json"


def codes(document: dict, filename: str = "test.yaml") -> list[str]:
    return [f.code for f in audit_document(document, filename)]


def ev(reference: str, **extra: object) -> dict:
    row = {"reference": reference, "snippet": "x", "supports": "SUPPORT"}
    row.update(extra)
    return row


class BackgroundOnlyTests(unittest.TestCase):
    def test_flags_support_that_is_entirely_background(self) -> None:
        document = {
            "pathophysiology": [
                {"name": "A", "evidence": [ev("PMID:1", quote_role="BACKGROUND")]}
            ]
        }
        self.assertIn("BACKGROUND_ONLY_SUPPORT", codes(document))

    def test_quiet_when_a_primary_result_is_also_attached(self) -> None:
        document = {
            "pathophysiology": [
                {
                    "name": "A",
                    "evidence": [
                        ev("PMID:1", quote_role="BACKGROUND"),
                        ev("PMID:2", quote_role="PRIMARY_RESULT"),
                    ],
                }
            ]
        }
        self.assertNotIn("BACKGROUND_ONLY_SUPPORT", codes(document))

    def test_absent_quote_role_is_not_treated_as_background(self) -> None:
        """quote_role is unset on most of the corpus; absence must not imply background."""
        document = {"pathophysiology": [{"name": "A", "evidence": [ev("PMID:1")]}]}
        self.assertNotIn("BACKGROUND_ONLY_SUPPORT", codes(document))

    def test_refuting_citations_do_not_count_as_support(self) -> None:
        document = {
            "pathophysiology": [
                {
                    "name": "A",
                    "evidence": [
                        ev("PMID:1", quote_role="BACKGROUND"),
                        ev("PMID:2", quote_role="PRIMARY_RESULT", supports="REFUTE"),
                    ],
                }
            ]
        }
        self.assertIn("BACKGROUND_ONLY_SUPPORT", codes(document))


class ScopingTests(unittest.TestCase):
    """Noisy detectors are scoped to mechanism claims."""

    def test_review_only_support_flags_a_mechanism_claim(self) -> None:
        document = {
            "pathophysiology": [
                {"name": "A", "evidence": [ev("PMID:1", quote_role="REVIEW_SYNTHESIS")]}
            ]
        }
        self.assertIn("REVIEW_ONLY_SUPPORT", codes(document))

    def test_review_only_support_ignores_a_treatment_entry(self) -> None:
        document = {
            "treatments": [
                {"name": "T", "evidence": [ev("PMID:1", quote_role="REVIEW_SYNTHESIS")]}
            ]
        }
        self.assertNotIn("REVIEW_ONLY_SUPPORT", codes(document))

    def test_unverifiable_support_flags_a_mechanism_claim(self) -> None:
        document = {"pathophysiology": [{"name": "A", "evidence": [ev("ORPHA:15")]}]}
        self.assertIn("UNVERIFIABLE_SOLE_SUPPORT", codes(document))

    def test_unverifiable_support_ignores_a_prevalence_entry(self) -> None:
        document = {"prevalence": [{"population": "x", "evidence": [ev("ORPHA:15")]}]}
        self.assertNotIn("UNVERIFIABLE_SOLE_SUPPORT", codes(document))

    def test_a_doi_or_pmc_reference_counts_as_verifiable(self) -> None:
        for reference in ("DOI:10.1000/abc", "url:https://pmc.ncbi.nlm.nih.gov/PMC1/"):
            document = {"pathophysiology": [{"name": "A", "evidence": [ev(reference)]}]}
            self.assertNotIn("UNVERIFIABLE_SOLE_SUPPORT", codes(document), reference)


class DirectEdgeTests(unittest.TestCase):
    def test_flags_only_when_no_endpoint_carries_evidence(self) -> None:
        document = {
            "pathophysiology": [
                {"name": "A", "downstream": [{"target": "B", "causal_link_type": "DIRECT"}]},
                {"name": "B"},
            ]
        }
        self.assertIn("DIRECT_EDGE_NO_EVIDENCE", codes(document))

    def test_quiet_when_the_source_node_carries_evidence(self) -> None:
        document = {
            "pathophysiology": [
                {
                    "name": "A",
                    "evidence": [ev("PMID:1")],
                    "downstream": [{"target": "B", "causal_link_type": "DIRECT"}],
                },
                {"name": "B"},
            ]
        }
        self.assertNotIn("DIRECT_EDGE_NO_EVIDENCE", codes(document))

    def test_quiet_when_the_target_node_carries_evidence(self) -> None:
        document = {
            "pathophysiology": [
                {"name": "A", "downstream": [{"target": "B", "causal_link_type": "DIRECT"}]},
                {"name": "B", "evidence": [ev("PMID:1")]},
            ]
        }
        self.assertNotIn("DIRECT_EDGE_NO_EVIDENCE", codes(document))

    def test_quiet_for_an_indirect_link(self) -> None:
        document = {
            "pathophysiology": [
                {
                    "name": "A",
                    "downstream": [
                        {"target": "B", "causal_link_type": "INDIRECT_UNKNOWN_INTERMEDIATES"}
                    ],
                },
                {"name": "B"},
            ]
        }
        self.assertNotIn("DIRECT_EDGE_NO_EVIDENCE", codes(document))


class HumanFrequencyTests(unittest.TestCase):
    def test_flags_a_human_frequency_backed_only_by_model_organism(self) -> None:
        document = {
            "phenotypes": [
                {
                    "name": "P",
                    "frequency": "VERY_FREQUENT",
                    "evidence": [ev("PMID:1", evidence_source="MODEL_ORGANISM")],
                }
            ]
        }
        self.assertIn("HUMAN_FREQUENCY_MODEL_ONLY", codes(document))

    def test_quiet_when_a_human_source_is_also_attached(self) -> None:
        document = {
            "phenotypes": [
                {
                    "name": "P",
                    "frequency": "VERY_FREQUENT",
                    "evidence": [
                        ev("PMID:1", evidence_source="MODEL_ORGANISM"),
                        ev("PMID:2", evidence_source="HUMAN_CLINICAL"),
                    ],
                }
            ]
        }
        self.assertNotIn("HUMAN_FREQUENCY_MODEL_ONLY", codes(document))

    def test_quiet_without_a_human_frequency_vocabulary_term(self) -> None:
        document = {
            "phenotypes": [
                {
                    "name": "P",
                    "frequency": "sometimes",
                    "evidence": [ev("PMID:1", evidence_source="MODEL_ORGANISM")],
                }
            ]
        }
        self.assertNotIn("HUMAN_FREQUENCY_MODEL_ONLY", codes(document))


class ConfidenceConflictTests(unittest.TestCase):
    def test_flags_established_confidence_with_refuting_evidence(self) -> None:
        document = {
            "pathophysiology": [
                {
                    "name": "A",
                    "mechanism_confidence": "ESTABLISHED",
                    "evidence": [ev("PMID:1"), ev("PMID:2", supports="REFUTE")],
                }
            ]
        }
        self.assertIn("CONFIDENCE_CONTRADICTS_EVIDENCE", codes(document))

    def test_quiet_when_confidence_is_provisional(self) -> None:
        document = {
            "pathophysiology": [
                {
                    "name": "A",
                    "mechanism_confidence": "PROVISIONAL",
                    "evidence": [ev("PMID:1"), ev("PMID:2", supports="REFUTE")],
                }
            ]
        }
        self.assertNotIn("CONFIDENCE_CONTRADICTS_EVIDENCE", codes(document))


class DualFormTests(unittest.TestCase):
    def test_flags_mixed_pmid_and_pmc_forms(self) -> None:
        document = {
            "pathophysiology": [
                {
                    "name": "A",
                    "evidence": [
                        ev("PMID:29635513"),
                        ev("url:https://pmc.ncbi.nlm.nih.gov/articles/PMC5961352/"),
                    ],
                }
            ]
        }
        self.assertIn("DUAL_FORM_CITATION", codes(document))

    def test_quiet_when_all_references_use_one_form(self) -> None:
        document = {
            "pathophysiology": [
                {"name": "A", "evidence": [ev("PMID:1"), ev("PMID:2")]}
            ]
        }
        self.assertNotIn("DUAL_FORM_CITATION", codes(document))


class DetectorContractTests(unittest.TestCase):
    def test_every_detector_states_its_false_positive_mode(self) -> None:
        for spec in detectors().values():
            self.assertTrue(spec.question.endswith("?"), spec.code)
            self.assertTrue(spec.false_positive_mode.strip(), spec.code)
            self.assertIsInstance(spec.severity, Severity)

    def test_an_ordinary_entry_produces_no_findings(self) -> None:
        document = {
            "pathophysiology": [
                {
                    "name": "A",
                    "evidence": [ev("PMID:1", quote_role="PRIMARY_RESULT")],
                    "downstream": [{"target": "B", "causal_link_type": "DIRECT",
                                    "evidence": [ev("PMID:2", quote_role="PRIMARY_RESULT")]}],
                },
                {"name": "B", "evidence": [ev("PMID:3", quote_role="PRIMARY_RESULT")]},
            ]
        }
        self.assertEqual(codes(document), [])


class CommittedAuditTests(unittest.TestCase):
    def test_committed_results_are_framed_as_review_flags(self) -> None:
        if not AUDIT.exists():
            self.skipTest("claim-fit audit not generated")
        payload = json.loads(AUDIT.read_text())
        self.assertIn("not a proven error", payload["framing"])
        self.assertEqual(payload["files_failed"], [])
        self.assertGreater(payload["files_examined"], 3000)
        for detector in payload["detectors"]:
            self.assertTrue(detector["false_positive_mode"])

    def test_dual_form_count_matches_the_independent_measurement(self) -> None:
        """Cross-check: a hand count of PMID+PMC co-occurrence gave 185."""
        if not AUDIT.exists():
            self.skipTest("claim-fit audit not generated")
        payload = json.loads(AUDIT.read_text())
        counts = {d["code"]: d["findings"] for d in payload["detectors"]}
        self.assertEqual(counts["DUAL_FORM_CITATION"], 185)


if __name__ == "__main__":
    unittest.main()
