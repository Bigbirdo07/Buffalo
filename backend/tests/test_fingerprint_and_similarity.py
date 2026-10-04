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


@pytest.mark.skipif(not FINGERPRINTS.exists(), reason="fingerprints not generated")
class TestCandidateRetrieval:
    """Retrieval must be broad enough to find real neighbours and honest enough
    to surface implausible ones for the refinement layer to reject."""

    @staticmethod
    @pytest.fixture(scope="class")
    def index():
        from atlas.services.candidate_generation import FeatureIndex

        records = [json.loads(line) for line in FINGERPRINTS.read_text().splitlines()]
        return FeatureIndex(records)

    @staticmethod
    def _query(index, name: str):
        from atlas.services.candidate_generation import generate_candidates

        disease_id = next(
            record["disease_id"]
            for record in index.fingerprints
            if record["disease_name"] == name
        )
        return generate_candidates(index, disease_id, limit=25)

    def test_non_discriminating_classes_are_excluded(self, index) -> None:
        # "Both diseases have a mouse model" is true of 1,036 diseases.
        for feature_id, feature_class in index.classes.items():
            assert feature_class not in {"model_organism", "therapeutic"}, feature_id

    def test_overly_common_features_are_not_retrieved_on(self, index) -> None:
        # "neuron" (548 diseases) would otherwise fuse most of the corpus.
        common = [key for key in index.postings if index.frequency(key) > 400]
        assert common
        assert all(not index.is_retrievable(key) for key in common)

    def test_same_gene_disease_ranks_first(self, index) -> None:
        # SCA48 is the dominant STUB1 disorder; SCAR16 is the recessive one.
        candidates = self._query(index, "Autosomal Recessive Spinocerebellar Ataxia 16")
        assert candidates[0].disease_name == "Spinocerebellar Ataxia 48"
        genes = {
            item.label
            for item in candidates[0].methods.get("SHARED_GENE_OR_PROTEIN", [])
        }
        assert "STUB1" in genes

    def test_method_scores_stay_separate(self, index) -> None:
        # A gene match and a phenotype match are different biological claims.
        candidates = self._query(index, "Autosomal Recessive Spinocerebellar Ataxia 16")
        assert len(candidates[0].scores) >= 4
        assert set(candidates[0].scores) == set(candidates[0].methods)

    def test_implausible_neighbour_is_retrieved_not_filtered(self, index) -> None:
        # Rabies shares Purkinje cell, mitophagy and myoclonus with SCAR16 while
        # being an acute viral encephalitis. Retrieval deliberately surfaces it:
        # suppressing it here would hide the case the refinement layer exists to
        # reject, and would make the counterexample invisible.
        candidates = self._query(index, "Autosomal Recessive Spinocerebellar Ataxia 16")
        names = {item.disease_name for item in candidates}
        assert "Rabies" in names
        rabies = next(item for item in candidates if item.disease_name == "Rabies")
        assert "SHARED_GENE_OR_PROTEIN" not in rabies.methods

    def test_retrieval_is_deterministic(self, index) -> None:
        first = self._query(index, "Autosomal Recessive Spinocerebellar Ataxia 16")
        second = self._query(index, "Autosomal Recessive Spinocerebellar Ataxia 16")
        assert [item.disease_id for item in first] == [item.disease_id for item in second]

    def test_unknown_disease_returns_empty_rather_than_raising(self, index) -> None:
        from atlas.services.candidate_generation import generate_candidates

        assert generate_candidates(index, "no-such-disease") == []


@pytest.mark.skipif(not FINGERPRINTS.exists(), reason="fingerprints not generated")
@pytest.mark.skipif(not HPO_PATH.exists(), reason="HPO snapshot not present")
class TestPairwiseComparison:
    """The comparison must separate a real neighbour from a phenotype-only one
    on grounds it can state, without deciding whether the relationship holds."""

    @staticmethod
    @pytest.fixture(scope="class")
    def setup():
        from atlas.services.candidate_generation import FeatureIndex, generate_candidates
        from atlas.services.disease_comparison import compare_diseases

        records = [json.loads(line) for line in FINGERPRINTS.read_text().splitlines()]
        index = FeatureIndex(records)
        ontology = HpoOntology.from_obo(HPO_PATH)
        sets = load_annotation_sets(ontology, [r["phenotype_ids"] for r in records])
        similarity = PhenotypeSimilarity(ontology, sets)
        phenotypes = {r["disease_id"]: s for r, s in zip(records, sets, strict=True)}
        query = next(
            r["disease_id"]
            for r in records
            if r["disease_name"] == "Autosomal Recessive Spinocerebellar Ataxia 16"
        )
        candidates = generate_candidates(index, query, limit=25)

        def build(name: str):
            candidate = next(c for c in candidates if c.disease_name == name)
            return compare_diseases(
                index, candidate, query, similarity,
                phenotypes[query], phenotypes[candidate.disease_id],
            )

        return build

    def test_same_gene_neighbour_is_molecularly_anchored(self, setup) -> None:
        comparison = setup("Spinocerebellar Ataxia 48")
        assert comparison.has_molecular_anchor
        assert "STUB1" in comparison.variant_compatibility.shared_genes

    def test_phenotype_only_neighbour_is_not_anchored(self, setup) -> None:
        # Lafora disease shares cerebellar phenotypes and a weak ubiquitination
        # term with SCAR16, but no gene and no strong process overlap.
        comparison = setup("Lafora_Disease")
        assert not comparison.has_molecular_anchor
        assert comparison.variant_compatibility.status.value == "NOT_ASSESSABLE"

    def test_implausible_neighbour_is_not_anchored_and_is_caveated(self, setup) -> None:
        # The counterexample: an acute viral encephalitis retrieved on mitophagy,
        # Purkinje cell and myoclonus. It must fail the anchor test and say why.
        comparison = setup("Rabies")
        assert not comparison.has_molecular_anchor
        assert comparison.strong_axes == ()
        assert any("phenotype and anatomy" in note for note in comparison.caveats)

    def test_unassessed_dimensions_are_declared_not_assumed_absent(self, setup) -> None:
        comparison = setup("Rabies")
        assert any(
            "unassessed rather than absent" in note for note in comparison.caveats
        )

    def test_shared_gene_with_same_direction_is_compatible(self, setup) -> None:
        comparison = setup("Spinocerebellar Ataxia 48")
        assert comparison.variant_compatibility.status.value == "COMPATIBLE"

    def test_no_shared_gene_blocks_variant_assessment(self, setup) -> None:
        comparison = setup("Rabies")
        assert comparison.variant_compatibility.status.value == "NOT_ASSESSABLE"
        assert "different proteins" in comparison.variant_compatibility.reason

    def test_comparison_states_no_verdict(self, setup) -> None:
        # The comparison describes; the refinement engine decides. If a status
        # field ever appears here, that separation has been lost.
        comparison = setup("Spinocerebellar Ataxia 48")
        assert not hasattr(comparison, "status")
        assert not hasattr(comparison, "refined_status")


class TestVariantCompatibilityRules:
    """The mandatory check: a shared gene symbol does not imply shared mechanism."""

    @staticmethod
    def _disease(name: str, effects: tuple[str, ...]) -> dict:
        return {"disease_name": name, "variant_effects": list(effects)}

    def test_opposite_directions_are_incompatible(self) -> None:
        from atlas.services.disease_comparison import assess_variant_compatibility

        result = assess_variant_compatibility(
            self._disease("A", ("loss_of_function", "nonsense")),
            self._disease("B", ("gain_of_function",)),
            ("GENEX",),
        )
        assert result.status.value == "INCOMPATIBLE"
        assert result.is_blocking

    def test_same_direction_is_compatible(self) -> None:
        from atlas.services.disease_comparison import assess_variant_compatibility

        result = assess_variant_compatibility(
            self._disease("A", ("nonsense",)),
            self._disease("B", ("frameshift",)),
            ("GENEX",),
        )
        assert result.status.value == "COMPATIBLE"

    def test_missing_annotation_is_not_assessable_rather_than_compatible(self) -> None:
        from atlas.services.disease_comparison import assess_variant_compatibility

        result = assess_variant_compatibility(
            self._disease("A", ("nonsense",)), self._disease("B", ()), ("GENEX",)
        )
        assert result.status.value == "NOT_ASSESSABLE"

    def test_no_shared_gene_is_not_assessable(self) -> None:
        from atlas.services.disease_comparison import assess_variant_compatibility

        result = assess_variant_compatibility(
            self._disease("A", ("nonsense",)), self._disease("B", ("missense",)), ()
        )
        assert result.status.value == "NOT_ASSESSABLE"


@pytest.mark.skipif(not FINGERPRINTS.exists(), reason="fingerprints not generated")
class TestMechanismClustering:
    @staticmethod
    @pytest.fixture(scope="class")
    def built():
        from atlas.services.candidate_generation import FeatureIndex
        from atlas.services.mechanism_clustering import build_mechanism_graph

        records = [json.loads(line) for line in FINGERPRINTS.read_text().splitlines()]
        index = FeatureIndex(records)
        graph, stats = build_mechanism_graph(index)
        return index, graph, stats

    def test_most_retrieved_pairs_are_rejected_as_unanchored(self, built) -> None:
        # The filter is doing the work: a pair linked only by phenotype and
        # anatomy must not be allowed to form a mechanism cluster.
        _index, _graph, stats = built
        assert stats["rejected_no_molecular_anchor"] > stats["edges"]

    def test_hub_genes_cannot_anchor_an_edge(self, built) -> None:
        # TP53 spans 98 diseases. "Both involve TP53" is not a mechanism claim,
        # and letting it anchor produced a 2,710-node giant component.
        from atlas.services.candidate_generation import SharedFeature
        from atlas.services.mechanism_clustering import Candidate, anchor_axes

        hub = SharedFeature(
            feature_id="HGNC:11998", label="TP53", feature_class="genetic",
            corpus_frequency=98, information_content=3.51,
            evidence_left=1, evidence_right=1,
        )
        candidate = Candidate(disease_id="x", disease_name="X", source_file="x.yaml")
        candidate.methods["SHARED_GENE_OR_PROTEIN"] = [hub]
        assert anchor_axes(candidate) == ()

    def test_specific_gene_does_anchor(self, built) -> None:
        from atlas.services.candidate_generation import SharedFeature
        from atlas.services.mechanism_clustering import Candidate, anchor_axes

        specific = SharedFeature(
            feature_id="HGNC:11427", label="STUB1", feature_class="genetic",
            corpus_frequency=3, information_content=7.0,
            evidence_left=1, evidence_right=1,
        )
        candidate = Candidate(disease_id="x", disease_name="X", source_file="x.yaml")
        candidate.methods["SHARED_GENE_OR_PROTEIN"] = [specific]
        assert anchor_axes(candidate) == ("SHARED_GENE_OR_PROTEIN",)

    def test_clusters_declare_when_they_have_no_statable_core(self, built) -> None:
        from atlas.services.mechanism_clustering import ClusterMethod, cluster_corpus

        index, graph, _stats = built
        clusters, _unclustered = cluster_corpus(index, graph, ClusterMethod.LOUVAIN)
        for cluster in clusters:
            if not cluster.has_statable_core:
                assert cluster.canonical_label == "NO_DEFENSIBLE_CLUSTER"
                assert cluster.caveats

    def test_stub1_disorders_cluster_together(self, built) -> None:
        from atlas.services.mechanism_clustering import ClusterMethod, cluster_corpus

        index, graph, _stats = built
        clusters, _unclustered = cluster_corpus(index, graph, ClusterMethod.LOUVAIN)
        query = next(
            r["disease_id"]
            for r in index.fingerprints
            if r["disease_name"] == "Autosomal Recessive Spinocerebellar Ataxia 16"
        )
        cluster = next(c for c in clusters if query in c.member_ids)
        # All three STUB1 disorders land together, found through shared biology
        # rather than through the gene symbol in the disease name.
        assert "Spinocerebellar Ataxia 48" in cluster.member_names
        assert "Cerebellar Ataxia-Hypogonadism Syndrome" in cluster.member_names
        assert cluster.has_statable_core

    def test_clustering_is_reproducible(self, built) -> None:
        from atlas.services.mechanism_clustering import ClusterMethod, cluster_corpus

        index, graph, _stats = built
        first, _ = cluster_corpus(index, graph, ClusterMethod.LOUVAIN)
        second, _ = cluster_corpus(index, graph, ClusterMethod.LOUVAIN)
        assert [c.member_ids for c in first] == [c.member_ids for c in second]
