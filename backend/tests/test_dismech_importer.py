from __future__ import annotations

import json
import unittest
from pathlib import Path

from atlas.adapters.dismech import DisMechImporter
from atlas.graph.algorithms import downstream_reach, structural_gap_candidates

FIXTURE = Path(__file__).parents[2] / "data" / "fixtures" / "dismech_demo_entry.json"


class DisMechImporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.importer = DisMechImporter(source_version="test-commit")
        self.imported = self.importer.load_path(FIXTURE)

    def test_identity_and_graph_import(self) -> None:
        self.assertEqual(self.imported.disease.mondo_id, "MONDO:0000001")
        # The live DisMech disease object carries no OMIM slot: OMIM identifiers reach
        # the entry through gene/external records, so omim_id is not populated at import.
        self.assertIsNone(self.imported.disease.omim_id)
        self.assertEqual(len(self.imported.graph.edges), 3)
        self.assertEqual(len(self.imported.phenotypes), 1)
        self.assertEqual(self.imported.phenotypes[0].hpo_id, "HP:0001270")

    def test_edge_evidence_is_not_copied_from_node(self) -> None:
        first_node = self.imported.graph.nodes[0]
        first_edge = self.imported.graph.edges[0]
        self.assertEqual(len(first_node.evidence_ids), 1)
        self.assertEqual(len(first_edge.evidence_ids), 2)
        self.assertTrue(set(first_node.evidence_ids).isdisjoint(first_edge.evidence_ids))

    def test_deterministic_reimport(self) -> None:
        second = self.importer.load_path(FIXTURE)
        self.assertEqual(self.imported.disease.id, second.disease.id)
        self.assertEqual(self.imported.graph.edges[0].id, second.graph.edges[0].id)
        self.assertEqual(self.imported.snapshot.sha256, second.snapshot.sha256)

    def test_variant_context_is_preserved_without_inferred_effect(self) -> None:
        self.assertEqual(
            {variant.upstream_label for variant in self.imported.variants},
            {"p.Gln100Ter", "p.Gly300Arg"},
        )
        self.assertEqual(
            {variant.variant_class for variant in self.imported.variants},
            {"nonsense", "missense"},
        )
        self.assertTrue(
            all(variant.functional_effect.value == "unknown" for variant in self.imported.variants),
            "upstream functional_effects text is preserved, never mapped to our enum",
        )
        # Upstream has no variant protein-domain slot, so none may be invented here.
        self.assertTrue(all(variant.protein_domain is None for variant in self.imported.variants))
        self.assertTrue(all(variant.source_object_path for variant in self.imported.variants))

    def test_discussion_gap_has_mandatory_pending_coverage(self) -> None:
        gap = self.imported.imported_gaps[0]
        self.assertIn("Domain B", gap.question)
        self.assertEqual(len(gap.search_coverage.sources), 7)
        self.assertTrue(
            all(item.status.value == "NOT_STARTED" for item in gap.search_coverage.sources)
        )

    def test_visible_candidate_dimensions(self) -> None:
        metrics = self.imported.candidate_metrics
        self.assertEqual(metrics.pathophysiology_nodes, 3)
        self.assertEqual(metrics.causal_edges, 3)
        self.assertEqual(metrics.variants, 2)
        self.assertEqual(metrics.explicit_gaps_or_controversies, 1)
        self.assertFalse(hasattr(metrics, "score"))

    def test_structural_gap_uses_downstream_dependence(self) -> None:
        first_edge = self.imported.graph.edges[0]
        self.assertEqual(downstream_reach(self.imported.graph, first_edge), 3)
        gaps = structural_gap_candidates(self.imported.graph)
        self.assertGreaterEqual(len(gaps), 1)
        self.assertIn("downstream", gaps[0].why_it_matters)

    def test_import_from_mapping_hashes_canonical_content(self) -> None:
        document = json.loads(FIXTURE.read_text())
        imported = self.importer.import_document(document, source_locator="fixture")
        self.assertEqual(len(imported.snapshot.sha256), 64)


if __name__ == "__main__":
    unittest.main()
