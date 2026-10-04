"""Tests for mechanistic fingerprints and ontology-aware phenotype comparison.

The calibration cases are pinned deliberately. The informative/generic threshold
was changed after inspecting SCAR16 vs SCAR20, so the two cases that drove the
change are tests: if someone retunes the threshold, these fail and say why.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas.adapters.dismech import DisMechImporter
from atlas.domain.fingerprint import FeatureClass
from atlas.services.fingerprint_builder import build_fingerprint
from atlas.services.hpo_similarity import (
    HpoOntology,
    PhenotypeSimilarity,
    compare_phenotypes,
    load_annotation_sets,
    unresolved_terms,
)

ROOT = Path(__file__).resolve().parents[2]
HPO_PATH = ROOT / "data/upstream/ontology/hp.obo"
FINGERPRINTS = ROOT / "data/fingerprints/fingerprints.jsonl"
DISORDERS = ROOT / "data/upstream/dismech-checkout/kb/disorders"

MINI_OBO = """format-version: 1.2

[Term]
id: HP:0000001
name: All

[Term]
id: HP:0000100
name: Abnormal nervous system
is_a: HP:0000001

[Term]
id: HP:0000200
name: Ataxia
is_a: HP:0000100

[Term]
id: HP:0000300
name: Cerebellar ataxia
is_a: HP:0000200

[Term]
id: HP:0000400
name: Nystagmus
is_a: HP:0000100
alt_id: HP:0009999

[Term]
id: HP:0000500
name: Obsolete thing
is_obsolete: true
replaced_by: HP:0000400
"""


@pytest.fixture(scope="module")
def mini() -> HpoOntology:
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".obo", delete=False) as handle:
        handle.write(MINI_OBO)
        path = Path(handle.name)
    return HpoOntology.from_obo(path)


class TestOntologyParsing:
    def test_parses_terms_and_parents(self, mini: HpoOntology) -> None:
        assert mini.terms["HP:0000300"].name == "Cerebellar ataxia"
        assert mini.terms["HP:0000300"].parents == ("HP:0000200",)

    def test_ancestor_closure_is_transitive(self, mini: HpoOntology) -> None:
        ancestors = mini.ancestors("HP:0000300")
        assert ancestors == {"HP:0000300", "HP:0000200", "HP:0000100", "HP:0000001"}

    def test_alt_id_resolves_to_primary(self, mini: HpoOntology) -> None:
        assert mini.canonical("HP:0009999") == "HP:0000400"

    def test_obsolete_term_follows_replaced_by(self, mini: HpoOntology) -> None:
        assert mini.canonical("HP:0000500") == "HP:0000400"

    def test_unknown_id_returns_none_rather_than_guessing(self, mini: HpoOntology) -> None:
        assert mini.canonical("HP:9999999") is None
        assert unresolved_terms(mini, ["HP:9999999", "HP:0000300"]) == ["HP:9999999"]


class TestInformationContent:
    def test_ic_rises_as_a_term_gets_rarer(self, mini: HpoOntology) -> None:
        sets = [
            frozenset({"HP:0000300"}),
            frozenset({"HP:0000400"}),
            frozenset({"HP:0000400"}),
            frozenset({"HP:0000400"}),
        ]
        sim = PhenotypeSimilarity(mini, sets)
        assert sim.ic("HP:0000300") > sim.ic("HP:0000400")

    def test_annotation_propagates_to_ancestors(self, mini: HpoOntology) -> None:
        sim = PhenotypeSimilarity(mini, [frozenset({"HP:0000300"})])
        # Annotating the child implies the parent, so the parent is counted.
        assert sim.term_counts["HP:0000200"] == 1

    def test_mica_picks_the_most_informative_common_ancestor(
        self, mini: HpoOntology
    ) -> None:
        sets = [frozenset({"HP:0000300"}), frozenset({"HP:0000400"})]
        sim = PhenotypeSimilarity(mini, sets)
        ancestor, _ic = sim.mica("HP:0000300", "HP:0000400")
        assert ancestor == "HP:0000100"

    def test_identical_sets_score_above_disjoint_sets(self, mini: HpoOntology) -> None:
        sets = [frozenset({"HP:0000300"}), frozenset({"HP:0000400"})]
        sim = PhenotypeSimilarity(mini, sets)
        same = sim.best_match_average(sets[0], sets[0])
        other = sim.best_match_average(sets[0], sets[1])
        assert same > other

    def test_empty_set_scores_zero_rather_than_erroring(self, mini: HpoOntology) -> None:
        sim = PhenotypeSimilarity(mini, [frozenset({"HP:0000300"})])
        assert sim.best_match_average(frozenset(), frozenset({"HP:0000300"})) == 0.0


@pytest.mark.skipif(not HPO_PATH.exists(), reason="HPO snapshot not present")
@pytest.mark.skipif(not FINGERPRINTS.exists(), reason="fingerprints not generated")
class TestRealCorpusCalibration:
    """The cases that drove the threshold change, pinned so a retune is visible."""

    @staticmethod
    @pytest.fixture(scope="class")
    def corpus() -> tuple[HpoOntology, PhenotypeSimilarity, list[dict], list[frozenset[str]]]:
        ontology = HpoOntology.from_obo(HPO_PATH)
        records = [json.loads(line) for line in FINGERPRINTS.read_text().splitlines()]
        sets = load_annotation_sets(ontology, [r["phenotype_ids"] for r in records])
        return ontology, PhenotypeSimilarity(ontology, sets), records, sets

    def test_every_corpus_hpo_id_resolves(self, corpus) -> None:
        ontology, _sim, records, _sets = corpus
        flat = [item for record in records for item in record["phenotype_ids"]]
        assert unresolved_terms(ontology, flat) == []

    def test_common_phenotypes_are_generic(self, corpus) -> None:
        # These dominate naive text or embedding similarity. Demoting them is the
        # whole reason for using the ontology.
        _ontology, sim, _records, _sets = corpus
        for term in ("HP:0001250", "HP:0001263", "HP:0001249", "HP:0001252"):
            assert not sim.is_informative(term), term

    def test_cerebellar_atrophy_is_informative(self, corpus) -> None:
        # The case that showed the 1% threshold was too strict: for two ataxias
        # this term is the overlap, not noise.
        _ontology, sim, _records, _sets = corpus
        assert sim.is_informative("HP:0001272")

    def test_related_ataxias_separate_from_an_unrelated_disease(self, corpus) -> None:
        _ontology, sim, records, sets = corpus
        index = {record["disease_name"]: position for position, record in enumerate(records)}
        scar16 = index["Autosomal Recessive Spinocerebellar Ataxia 16"]
        scar20 = index["Autosomal Recessive Spinocerebellar Ataxia 20"]
        unrelated = index["Alpha-1 Antitrypsin Deficiency"]
        near = compare_phenotypes(sim, sets[scar16], sets[scar20])
        far = compare_phenotypes(sim, sets[scar16], sets[unrelated])
        assert near.best_match_average > far.best_match_average
        assert near.has_informative_overlap
        assert not far.has_informative_overlap

    def test_comparison_partitions_every_shared_term(self, corpus) -> None:
        _ontology, sim, _records, sets = corpus
        comparison = compare_phenotypes(sim, sets[375], sets[376])
        shared = len(sets[375] & sets[376])
        assert len(comparison.shared_informative) + len(comparison.shared_generic) == shared


@pytest.mark.skipif(not DISORDERS.exists(), reason="upstream checkout not present")
class TestFingerprintBuilder:
    @staticmethod
    @pytest.fixture(scope="class")
    def fingerprint():
        importer = DisMechImporter(source_version="test")
        path = DISORDERS / "Autosomal_Recessive_Spinocerebellar_Ataxia_16.yaml"
        return build_fingerprint(importer.load_path(path))

    def test_every_feature_carries_provenance(self, fingerprint) -> None:
        # The rule that makes a candidate neighbour traceable: no bare strings.
        for feature in fingerprint.features:
            assert feature.source_object_paths, feature.feature_id

    def test_phenotypes_and_genes_are_grounded(self, fingerprint) -> None:
        assert fingerprint.phenotype_ids
        assert all(item.startswith("HP:") for item in fingerprint.phenotype_ids)
        assert any(item.startswith("HGNC:") for item in fingerprint.gene_ids)

    def test_coverage_counts_match_the_feature_list(self, fingerprint) -> None:
        assert sum(fingerprint.coverage.features_by_class.values()) == len(
            fingerprint.features
        )
        grounded = sum(1 for item in fingerprint.features if item.is_ontology_grounded)
        assert fingerprint.coverage.ontology_grounded_features == grounded

    def test_missing_dimensions_are_declared(self, fingerprint) -> None:
        # A dimension the source does not cover is a limit on every comparison
        # using this fingerprint, so it must be stated rather than inferred.
        for dimension in fingerprint.coverage.missing_dimensions:
            assert fingerprint.coverage.features_by_class.get(dimension, 0) == 0

    def test_feature_classes_resolve(self, fingerprint) -> None:
        assert fingerprint.features_of(FeatureClass.PHENOTYPE)
        assert fingerprint.feature_ids(FeatureClass.PHENOTYPE) <= fingerprint.feature_ids()

    def test_fingerprint_is_deterministic(self, fingerprint) -> None:
        importer = DisMechImporter(source_version="test")
        path = DISORDERS / "Autosomal_Recessive_Spinocerebellar_Ataxia_16.yaml"
        again = build_fingerprint(importer.load_path(path))
        assert [item.feature_id for item in again.features] == [
            item.feature_id for item in fingerprint.features
        ]
        assert again.source_sha256 == fingerprint.source_sha256
