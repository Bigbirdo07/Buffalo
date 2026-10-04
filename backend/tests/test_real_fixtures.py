"""Regression tests over fixtures derived from real DisMech entries.

Each fixture is a trimmed copy of a real upstream file; data/fixtures/real/MANIFEST.json
records the upstream filename, pinned commit, upstream SHA-256 and trim rule.
"""

from __future__ import annotations

import json
import unittest
from hashlib import sha256
from pathlib import Path

from atlas.adapters.dismech import DisMechImporter
from atlas.adapters.dismech.field_audit import FieldDisposition
from atlas.adapters.dismech.importer import ImportedDisease
from atlas.domain.provenance import ProvenanceKind

ROOT = Path(__file__).parents[2]
FIXTURE_DIR = ROOT / "data" / "fixtures" / "real"
MANIFEST = json.loads((FIXTURE_DIR / "MANIFEST.json").read_text())
COMMIT = "b923d18f1c962eeaecf9f1f908305b21a8f26904"


def load(name: str) -> ImportedDisease:
    importer = DisMechImporter(source_version=COMMIT)
    return importer.load_path(FIXTURE_DIR / name)


class FixtureProvenanceTests(unittest.TestCase):
    def test_manifest_matches_fixture_bytes(self) -> None:
        for entry in MANIFEST["fixtures"]:
            path = FIXTURE_DIR / entry["fixture"]
            digest = sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, entry["fixture_sha256"], entry["fixture"])
            self.assertEqual(entry["dismech_commit"], COMMIT)
            self.assertTrue(entry["upstream_file"].startswith("kb/disorders/"))
            self.assertRegex(entry["upstream_sha256"], r"^[0-9a-f]{64}$")

    def test_manifest_records_extraction_procedure(self) -> None:
        rule = MANIFEST["trim_rule"]
        self.assertEqual(MANIFEST["generator"], "scripts/build_fixtures.py")
        self.assertIn("pathophysiology", rule["sections_kept_whole"])
        self.assertIn("phenotypes", rule["sections_kept_whole"])
        self.assertGreaterEqual(rule["evidence_list_cap"], 2)

    def test_every_fixture_is_covered(self) -> None:
        listed = {entry["fixture"] for entry in MANIFEST["fixtures"]}
        found = {path.name for path in FIXTURE_DIR.glob("*.yaml")}
        self.assertEqual(listed, found)
        self.assertGreaterEqual(len(found), 3)


class RealImportTests(unittest.TestCase):
    def test_no_silent_loss_in_any_real_fixture(self) -> None:
        for entry in MANIFEST["fixtures"]:
            with self.subTest(entry["fixture"]):
                imported = load(entry["fixture"])
                audit = imported.field_audit
                self.assertEqual(audit.undeclared_paths, ())
                self.assertEqual(audit.unretained_top_level_paths, ())
                self.assertEqual(audit.silently_dropped_count, 0)

    def test_audit_separates_normalized_from_preserved(self) -> None:
        audit = load("scar16.yaml").field_audit
        normalized = audit.paths_with(FieldDisposition.NORMALIZED)
        preserved = audit.paths_with(FieldDisposition.PRESERVED_UNNORMALIZED)
        self.assertTrue(normalized)
        self.assertTrue(preserved)
        self.assertTrue(
            {"$.pathophysiology[].name", "$.pathophysiology[].downstream[].target"}
            <= {item.path for item in normalized}
        )
        self.assertIn("$.treatments", {item.path for item in preserved})

    def test_nested_ontology_identifiers_are_read(self) -> None:
        imported = load("scar16.yaml")
        self.assertEqual(imported.disease.mondo_id, "MONDO:0014339")
        self.assertEqual([gene.hgnc_id for gene in imported.genes], ["HGNC:11427"])
        curies = {
            annotation.term_id
            for node in imported.graph.nodes
            for annotation in node.annotations
            if annotation.term_id
        }
        self.assertIn("HGNC:11427", curies)
        self.assertTrue(any(curie.startswith("GO:") for curie in curies))
        self.assertTrue(all(phenotype.hpo_id for phenotype in imported.phenotypes))

    def test_lowercase_upstream_curies_are_normalized(self) -> None:
        raw = (FIXTURE_DIR / "scar16.yaml").read_text()
        self.assertIn("hgnc:11427", raw)  # upstream writes the prefix in lower case
        self.assertEqual(load("scar16.yaml").genes[0].hgnc_id, "HGNC:11427")

    def test_phenotype_sequelae_become_causal_edges(self) -> None:
        imported = load("scar16.yaml")
        sequelae = [
            edge
            for edge in imported.graph.edges
            if ".sequelae[" in edge.provenance.source_object_path
        ]
        self.assertTrue(sequelae)
        for edge in sequelae:
            self.assertEqual(edge.predicate, "CAUSES_OR_CONTRIBUTES_TO")
            self.assertIn(edge.subject_id, {node.id for node in imported.graph.nodes})
            self.assertIn(edge.object_id, {node.id for node in imported.graph.nodes})

    def test_evidence_metadata_is_preserved(self) -> None:
        imported = load("scar16.yaml")
        with_explanation = [item for item in imported.evidence if item.curator_explanation]
        with_directness = [item for item in imported.evidence if item.upstream_directness]
        self.assertTrue(with_explanation)
        self.assertTrue(with_directness)
        refuting = [
            item for item in imported.evidence if item.evidence_relation.value == "refutes"
        ]
        self.assertTrue(refuting, "SCAR16 carries upstream REFUTE evidence")
        self.assertTrue(all(item.exact_supported_span.strip() for item in imported.evidence))

    def test_variants_and_models_are_represented(self) -> None:
        imported = load("scar16.yaml")
        self.assertTrue(imported.variants)
        self.assertTrue(any(variant.upstream_label for variant in imported.variants))
        self.assertTrue(
            all(variant.functional_effect.value == "unknown" for variant in imported.variants),
            "functional effect is never inferred at import",
        )
        sections = {record.section for record in imported.preserved_records}
        self.assertIn("animal_models", sections)
        self.assertIn("experimental_models", sections)

    def test_discussions_only_become_gaps_for_knowledge_gap_kind(self) -> None:
        imported = load("acan_short_stature.yaml")
        kinds = {
            str(record.provenance.source_payload.get("kind"))
            for record in imported.preserved_records
            if record.section == "discussions"
        }
        self.assertIn("CONTROVERSY", kinds)
        self.assertIn("KNOWLEDGE_GAP", kinds)
        self.assertEqual(len(imported.imported_gaps), 1)
        for gap in imported.imported_gaps:
            self.assertTrue(
                all(
                    source.status.value == "NOT_STARTED"
                    for source in gap.search_coverage.sources
                ),
                "an imported gap must not claim searches it did not run",
            )

    def test_multiple_hypotheses_keep_upstream_status(self) -> None:
        imported = load("wilson_disease.yaml")
        self.assertGreater(len(imported.hypotheses), 1)
        statuses = {hypothesis.upstream_status for hypothesis in imported.hypotheses}
        self.assertTrue({"CANONICAL", "EMERGING"} <= statuses)

    def test_entry_without_discussions_imports(self) -> None:
        imported = load("sanfilippo.yaml")
        self.assertEqual(imported.imported_gaps, ())
        self.assertTrue(imported.graph.edges)

    def test_preserved_records_keep_source_path_and_hash(self) -> None:
        imported = load("wilson_disease.yaml")
        self.assertTrue(imported.preserved_records)
        for record in imported.preserved_records:
            self.assertRegex(record.payload_sha256, r"^[0-9a-f]{64}$")
            self.assertTrue(record.provenance.source_object_path)
            self.assertEqual(
                record.provenance.source_snapshot_sha256, imported.snapshot.sha256
            )
            self.assertEqual(record.provenance.kind, ProvenanceKind.CURATED)
            self.assertTrue(record.reason)

    def test_import_is_deterministic(self) -> None:
        first, second = load("acan_short_stature.yaml"), load("acan_short_stature.yaml")
        self.assertEqual(first.snapshot.sha256, second.snapshot.sha256)
        self.assertEqual(
            [edge.id for edge in first.graph.edges], [edge.id for edge in second.graph.edges]
        )
        self.assertEqual(
            [item.evidence_id for item in first.evidence],
            [item.evidence_id for item in second.evidence],
        )

    def test_absolute_and_relative_paths_produce_identical_ids(self) -> None:
        source = FIXTURE_DIR / "scar16.yaml"
        relative = source.relative_to(ROOT)
        importer = DisMechImporter(source_version=COMMIT)
        absolute_import = importer.load_path(source.resolve())
        relative_import = importer.load_path(relative)
        self.assertEqual(absolute_import.disease.id, relative_import.disease.id)
        self.assertEqual(
            [claim.claim_id for claim in absolute_import.claims],
            [claim.claim_id for claim in relative_import.claims],
        )
        self.assertEqual(
            [edge.id for edge in absolute_import.graph.edges],
            [edge.id for edge in relative_import.graph.edges],
        )

    def test_dangling_edge_targets_are_warned_not_dropped(self) -> None:
        imported = load("sanfilippo.yaml")
        warnings = [item for item in imported.warnings if item.code == "DANGLING_EDGE_TARGET"]
        self.assertTrue(warnings)
        node_ids = {node.id for node in imported.graph.nodes}
        for edge in imported.graph.edges:
            self.assertIn(edge.object_id, node_ids, "a dangling target still gets a node")

    def test_upstream_claims_are_curated_and_unreviewed(self) -> None:
        imported = load("scar16.yaml")
        for claim in imported.claims:
            self.assertEqual(claim.claim_type.value, "curated")
            self.assertEqual(claim.refinement_status.value, "UNREVIEWED")
            self.assertEqual(claim.provenance.source_name, "DisMech")
            self.assertEqual(claim.provenance.source_version, COMMIT)


if __name__ == "__main__":
    unittest.main()
