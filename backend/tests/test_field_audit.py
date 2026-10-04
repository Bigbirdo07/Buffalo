"""Tests for the field-disposition audit.

The audit is the mechanism behind the "zero silently dropped fields" claim, so it
must fail loudly when an upstream field has no declared handling. The decisive
test injects fields that do not exist upstream and asserts they are reported.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

from atlas.adapters.dismech import DisMechImporter
from atlas.adapters.dismech.field_audit import (
    FieldDisposition,
    audit_fields,
    normalize_path,
    observed_paths,
    resolve,
)

ROOT = Path(__file__).parents[2]
REAL = ROOT / "data" / "fixtures" / "real" / "scar16.yaml"
COMMIT = "b923d18f1c962eeaecf9f1f908305b21a8f26904"


class PathNormalizationTests(unittest.TestCase):
    def test_list_indices_collapse(self) -> None:
        self.assertEqual(
            normalize_path("$.pathophysiology[11].downstream[2].evidence[0].snippet"),
            "$.pathophysiology[].downstream[].evidence[].snippet",
        )

    def test_observed_paths_counts_occurrences(self) -> None:
        counts = observed_paths({"a": [{"b": 1}, {"b": 2}], "c": 3})
        self.assertEqual(counts["$.a[].b"], 2)
        self.assertEqual(counts["$.c"], 1)


class DispositionTests(unittest.TestCase):
    def test_graph_bearing_fields_are_normalized(self) -> None:
        for path in (
            "$.name",
            "$.pathophysiology[].name",
            "$.pathophysiology[].downstream[].target",
            "$.pathophysiology[].downstream[].evidence[].snippet",
            "$.phenotypes[].phenotype_term.term.id",
            "$.genetic[].gene_term.term.id",
        ):
            with self.subTest(path):
                self.assertEqual(resolve(path)[0], FieldDisposition.NORMALIZED)

    def test_unmodeled_sections_are_preserved_not_normalized(self) -> None:
        for path in ("$.treatments", "$.diagnosis", "$.clinical_trials", "$.classifications"):
            with self.subTest(path):
                disposition, target = resolve(path)
                self.assertEqual(disposition, FieldDisposition.PRESERVED_UNNORMALIZED)
                self.assertIn("PreservedUpstreamRecord", target)

    def test_unknown_child_of_a_known_section_is_preserved(self) -> None:
        disposition, target = resolve("$.pathophysiology[].some_future_slot")
        self.assertEqual(disposition, FieldDisposition.PRESERVED_UNNORMALIZED)
        self.assertIn("source_payload", target)

    def test_unknown_top_level_section_is_undeclared(self) -> None:
        self.assertEqual(
            resolve("$.some_entirely_new_section")[0], FieldDisposition.UNDECLARED
        )

    def test_unknown_field_under_a_declared_child_is_undeclared(self) -> None:
        """A wildcard on a parent must not silently absorb new evidence subfields."""
        self.assertEqual(
            resolve("$.pathophysiology[].evidence[].brand_new_qualifier")[0],
            FieldDisposition.UNDECLARED,
        )


class AuditAgainstRealDataTests(unittest.TestCase):
    def test_real_entry_has_no_undeclared_or_unretained_paths(self) -> None:
        imported = DisMechImporter(source_version=COMMIT).load_path(REAL)
        audit = imported.field_audit
        self.assertEqual(audit.undeclared_paths, ())
        self.assertEqual(audit.unretained_top_level_paths, ())

    def test_injected_unknown_fields_are_reported(self) -> None:
        document = yaml.safe_load(REAL.read_text())
        document["speculative_new_section"] = [{"name": "x"}]
        document["pathophysiology"][0]["evidence"][0]["speculative_qualifier"] = "y"
        audit = audit_fields(document, retained_object_paths=set())
        self.assertIn("$.speculative_new_section", audit.undeclared_paths)
        self.assertIn(
            "$.pathophysiology[].evidence[].speculative_qualifier", audit.undeclared_paths
        )
        self.assertGreater(audit.silently_dropped_count, 0)

    def test_unretained_top_level_items_are_reported(self) -> None:
        document = yaml.safe_load(REAL.read_text())
        audit = audit_fields(document, retained_object_paths=set())
        self.assertTrue(
            audit.unretained_top_level_paths,
            "with nothing retained, every non-identity item must be reported as lost",
        )

    def test_importer_warns_on_an_unknown_top_level_section(self) -> None:
        document = yaml.safe_load(REAL.read_text())
        document["speculative_new_section"] = [{"name": "x"}]
        imported = DisMechImporter(source_version=COMMIT).import_document(
            document, source_locator="kb/disorders/injected.yaml"
        )
        codes = {warning.code for warning in imported.warnings}
        self.assertIn("UNDECLARED_TOP_LEVEL_SECTION", codes)
        sections = {record.section for record in imported.preserved_records}
        self.assertIn(
            "speculative_new_section",
            sections,
            "an undeclared section is still preserved verbatim, not dropped",
        )

    def test_missing_evidence_snippet_warns_and_cannot_create_support(self) -> None:
        document = yaml.safe_load(REAL.read_text())
        evidence = document["pathophysiology"][0]["evidence"][0]
        evidence.pop("snippet")
        imported = DisMechImporter(source_version=COMMIT).import_document(
            document, source_locator="kb/disorders/missing-snippet.yaml"
        )
        warnings = [
            warning for warning in imported.warnings if warning.code == "EVIDENCE_WITHOUT_SNIPPET"
        ]
        self.assertEqual(len(warnings), 1)
        self.assertNotIn(
            "pathophysiology[0].evidence[0]",
            {item.provenance.source_object_path for item in imported.evidence},
        )

    def test_audit_observation_counts_are_reported(self) -> None:
        imported = DisMechImporter(source_version=COMMIT).load_path(REAL)
        observations = {item.path: item for item in imported.field_audit.observations}
        self.assertGreater(observations["$.pathophysiology[].name"].occurrences, 1)
        self.assertTrue(observations["$.pathophysiology[].name"].target)

    def test_every_observation_carries_a_disposition_and_target(self) -> None:
        imported = DisMechImporter(source_version=COMMIT).load_path(REAL)
        for item in imported.field_audit.observations:
            self.assertIsInstance(item.disposition, FieldDisposition)
            self.assertTrue(item.target)


class CorpusAuditSummaryTests(unittest.TestCase):
    """Checks the committed whole-corpus audit summary, when present."""

    SUMMARY = ROOT / "data" / "audit" / "corpus_audit.json"

    def test_summary_reports_zero_silent_loss(self) -> None:
        if not self.SUMMARY.exists():  # pragma: no cover - produced by scripts/audit_corpus.py
            self.skipTest("corpus audit summary not generated")
        summary = json.loads(self.SUMMARY.read_text())
        self.assertEqual(summary["dismech_commit"], COMMIT)
        self.assertEqual(summary["totals"]["undeclared_paths"], 0)
        self.assertEqual(summary["totals"]["unretained_top_level_items"], 0)
        self.assertEqual(summary["totals"]["files_failed"], 0)
        self.assertGreater(summary["totals"]["files_imported"], 3000)


if __name__ == "__main__":
    unittest.main()
