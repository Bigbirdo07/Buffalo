"""Tests for the retrieval/evidence separation and identity detection.

The SCAR16-derived cases here are regression fixtures, not rules. A test asserts
that no disease, gene or pathway name appears in the application code.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from atlas.domain.cross_disease import (
    CompatibilityVerdict,
    IdentityRelation,
    ReasonType,
    RejectedCrossDiseaseCandidate,
    RelationshipClass,
    RetrievalReason,
    RetrievalValidity,
    ReviewStatus,
    ValidatedRelationship,
)
from atlas.services.disease_identity import (
    IdentitySignals,
    _core_name,
    classify_identity,
)

ROOT = Path(__file__).resolve().parents[2]
FINGERPRINTS = ROOT / "data/fingerprints/fingerprints.jsonl"
HPO_PATH = ROOT / "data/upstream/ontology/hp.obo"


def _reason(**kw) -> RetrievalReason:
    base = dict(
        disease_a="a", disease_b="b", reason_type=ReasonType.SHARED_GO_TERM,
        source_feature="GO:0016567", generating_algorithm="feature-index",
        algorithm_version="v1",
    )
    base.update(kw)
    return RetrievalReason.create(**base)


class TestRetrievalIsNotEvidence:
    def test_retrieval_reason_is_never_evidence(self) -> None:
        assert _reason().is_biological_evidence is False

    def test_retrieval_reason_carries_no_evidence_field(self) -> None:
        # Structural guarantee: there is nowhere to put evidence on a retrieval
        # reason, so it cannot masquerade as one.
        assert "evidence_ids" not in RetrievalReason.model_fields

    def test_retrieval_reason_id_is_deterministic_and_order_free(self) -> None:
        left = _reason(disease_a="x", disease_b="y")
        right = _reason(disease_a="y", disease_b="x")
        assert left.retrieval_reason_id == right.retrieval_reason_id

    def test_mechanistic_class_requires_evidence(self) -> None:
        # The core rule: annotation overlap cannot produce a mechanism claim.
        with pytest.raises(ValueError, match="requires evidence_ids"):
            ValidatedRelationship(
                relationship_id="r1", disease_a="a", disease_b="b",
                relationship_class=RelationshipClass.SHARED_CAUSAL_MECHANISM,
                mechanistic_statement="shared annotation", source_version="v",
            )

    def test_non_mechanistic_class_needs_no_evidence(self) -> None:
        relationship = ValidatedRelationship(
            relationship_id="r2", disease_a="a", disease_b="b",
            relationship_class=RelationshipClass.SHARED_PHENOTYPE_ONLY,
            mechanistic_statement="symptom overlap only", source_version="v",
        )
        assert not relationship.asserts_shared_mechanism


class TestRetrievalValidityRegressionCases:
    """The four Phase 5 outcomes, encoded as expectations rather than rules."""

    def test_wrong_explanation_with_real_connection_is_representable(self) -> None:
        # The case that motivated the redesign: retrieved on a broad ontology
        # term, genuine for an unrelated documented reason.
        relationship = ValidatedRelationship(
            relationship_id="r3", disease_a="a", disease_b="b",
            relationship_class=RelationshipClass.SHARED_DOWNSTREAM_MECHANISM,
            mechanistic_statement=(
                "Direct physical interaction in a shared stress-response complex."
            ),
            retrieval_validity=RetrievalValidity.INCORRECT_BUT_CONNECTION_REAL,
            evidence_ids=("PMID:19892702", "PMID:21652633"),
            source_version="v",
        )
        assert relationship.retrieval_explanation_was_wrong
        assert relationship.asserts_shared_mechanism

    def test_broad_ontology_overlap_with_differing_chemistry(self) -> None:
        relationship = ValidatedRelationship(
            relationship_id="r4", disease_a="a", disease_b="b",
            relationship_class=(
                RelationshipClass.SHARED_CELLULAR_PROCESS_NON_EQUIVALENT
            ),
            mechanistic_statement="Same process term, opposite biochemistry.",
            retrieval_validity=RetrievalValidity.INCORRECT_AND_CONNECTION_FALSE,
            directionality_compatibility=CompatibilityVerdict.INCOMPATIBLE,
            source_version="v",
        )
        assert not relationship.asserts_shared_mechanism
        assert relationship.retrieval_explanation_was_wrong

    def test_ontology_hub_artifact_is_representable(self) -> None:
        relationship = ValidatedRelationship(
            relationship_id="r5", disease_a="a", disease_b="b",
            relationship_class=RelationshipClass.RETRIEVAL_ARTIFACT,
            mechanistic_statement="",
            retrieval_validity=RetrievalValidity.INCORRECT_AND_CONNECTION_FALSE,
            source_version="v",
        )
        assert relationship.relationship_class is RelationshipClass.RETRIEVAL_ARTIFACT

    def test_allelic_spectrum_is_not_counted_as_discovery(self) -> None:
        # Two labels for one spectrum must not inflate cross-disease findings.
        relationship = ValidatedRelationship(
            relationship_id="r6", disease_a="a", disease_b="b",
            relationship_class=RelationshipClass.SHARED_CAUSAL_MECHANISM,
            mechanistic_statement="Same gene, same mechanism.",
            evidence_ids=("PMID:1",),
            identity_relation=IdentityRelation.ALLELIC_SPECTRUM,
            source_version="v",
        )
        assert relationship.asserts_shared_mechanism
        assert not relationship.is_independent_discovery

    def test_distinct_disease_mechanism_counts_as_discovery(self) -> None:
        relationship = ValidatedRelationship(
            relationship_id="r7", disease_a="a", disease_b="b",
            relationship_class=RelationshipClass.SHARED_DOWNSTREAM_MECHANISM,
            mechanistic_statement="Converge on one node.",
            evidence_ids=("PMID:1",),
            identity_relation=IdentityRelation.DISTINCT_DISEASE,
            source_version="v",
        )
        assert relationship.is_independent_discovery


class TestRelationshipVersioning:
    def test_supersede_preserves_prior_classification(self) -> None:
        original = ValidatedRelationship(
            relationship_id="r8", disease_a="a", disease_b="b",
            relationship_class=RelationshipClass.INSUFFICIENT_EVIDENCE,
            mechanistic_statement="", source_version="v",
        )
        updated = original.supersede(
            RelationshipClass.SHARED_DOWNSTREAM_MECHANISM,
            evidence_ids=("PMID:1",),
            mechanistic_statement="New evidence.",
        )
        assert updated.superseded_classes == ("INSUFFICIENT_EVIDENCE",)
        assert updated.last_reviewed_at is not None
        # The original object is frozen and unchanged.
        assert original.relationship_class is RelationshipClass.INSUFFICIENT_EVIDENCE


class TestRejectedCandidatesArePreserved:
    def test_rejected_candidate_keeps_its_null_searches(self) -> None:
        rejected = RejectedCrossDiseaseCandidate(
            rejection_id="x1", disease_a="a", disease_b="b",
            retrieval_reason_ids=("rr1",),
            rejected_class=RelationshipClass.SHARED_PHENOTYPE_ONLY,
            retrieval_validity=RetrievalValidity.INCORRECT_AND_CONNECTION_FALSE,
            reason="Shared anatomy, unrelated cellular route.",
            null_searches=("(a) AND (b): 8 hits, none on topic",),
        )
        assert rejected.null_searches


class TestIdentityDetectionIsGeneral:
    @staticmethod
    def _signals(**kw) -> IdentitySignals:
        base = dict(
            shared_genes=("HGNC:1",), only_genes_a=(), only_genes_b=(),
            phenotype_overlap=0.6, shared_phenotype_count=6,
            name_core_match=False, same_mondo=False,
        )
        base.update(kw)
        return IdentitySignals(**base)

    def test_same_mondo_is_same_disease(self) -> None:
        relation, _ = classify_identity(self._signals(same_mondo=True))
        assert relation is IdentityRelation.SAME_DISEASE

    def test_identical_genes_and_high_overlap_is_allelic_spectrum(self) -> None:
        relation, rationale = classify_identity(self._signals())
        assert relation is IdentityRelation.ALLELIC_SPECTRUM
        assert "not a cross-disease discovery" in rationale

    def test_identical_genes_low_overlap_needs_review_not_merge(self) -> None:
        # One gene can produce mechanistically distinct disorders, so this must
        # not auto-merge.
        relation, _ = classify_identity(self._signals(phenotype_overlap=0.1))
        assert relation is IdentityRelation.PARTIALLY_OVERLAPPING_ENTITY

    def test_no_shared_gene_is_distinct(self) -> None:
        relation, _ = classify_identity(self._signals(shared_genes=()))
        assert relation is IdentityRelation.DISTINCT_DISEASE

    def test_series_designations_do_not_make_different_diseases(self) -> None:
        assert _core_name("Spinocerebellar Ataxia Type 48") == _core_name(
            "Autosomal Recessive Spinocerebellar Ataxia 16"
        )

    def test_unrelated_names_do_not_collapse(self) -> None:
        assert _core_name("Lafora Disease") != _core_name("Rabies")

    def test_non_distinct_verdicts_request_expert_signoff(self) -> None:
        from atlas.services.disease_identity import assess_identity
        from atlas.services.hpo_similarity import HpoOntology, PhenotypeSimilarity

        if not HPO_PATH.exists():
            pytest.skip("HPO snapshot not present")
        ontology = HpoOntology.from_obo(HPO_PATH)
        similarity = PhenotypeSimilarity(ontology, [frozenset({"HP:0001251"})])
        left = {
            "disease_id": "d1", "disease_name": "Example Disorder Type 1",
            "gene_ids": ["HGNC:1"], "mondo_id": None,
        }
        right = {
            "disease_id": "d2", "disease_name": "Example Disorder Type 2",
            "gene_ids": ["HGNC:1"], "mondo_id": None,
        }
        result = assess_identity(
            left, right, similarity,
            frozenset({"HP:0001251"}), frozenset({"HP:0001251"}),
        )
        assert result.relation is IdentityRelation.ALLELIC_SPECTRUM
        assert result.review_status is ReviewStatus.AWAITING_EXPERT_SIGNOFF
        assert not result.is_independent_pair


class TestNoSpecialCaseLogic:
    """Hard requirement: scientific behaviour must be general.

    Comments and docstrings may cite the cases that motivated a rule -- that is
    how a reader checks the reasoning. Executable code may not branch on them.
    Docstrings are excluded by parsing the AST rather than by guessing at line
    prefixes, because a naive prefix check misses continuation lines.
    """

    # Empty, and it must stay that way. Both Phase 4 action modules carried
    # single-gene search literals until the queries were rebuilt from structured
    # context. An entry here is a licence to be disease-specific, so adding one
    # should take a deliberate edit and a reason.
    KNOWN_DISEASE_SPECIFIC: dict[str, str] = {}

    BANNED = re.compile(
        r"\b(SCAR16|STUB1|CHIP|Lafora|malin|NHLRC1|Rabies|PEX\d+|TP53|"
        r"Purkinje|SCA48)\b"
    )

    @classmethod
    def _code_lines(cls, path: Path) -> list[tuple[int, str]]:
        """Lines of real code, with docstrings and comments removed.

        Only *docstrings* are exempt, not every string literal. A hardcoded
        search query naming one gene is disease-specific application data even
        though it is a string, and masking all literals would hide exactly the
        kind of special-casing this test exists to find.
        """
        import ast

        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        masked: set[int] = set()
        for node in ast.walk(tree):
            if not isinstance(
                node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
            ):
                continue
            body = getattr(node, "body", None)
            if not body:
                continue
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                end = first.value.end_lineno or first.value.lineno
                masked.update(range(first.value.lineno, end + 1))
        rows: list[tuple[int, str]] = []
        for number, line in enumerate(source.splitlines(), start=1):
            if number in masked:
                continue
            code = line.split("#", 1)[0].strip()
            if code:
                rows.append((number, code))
        return rows

    def test_new_cross_disease_code_is_disease_agnostic(self) -> None:
        offenders: list[str] = []
        for path in (ROOT / "backend/src/atlas").rglob("*.py"):
            if path.name in self.KNOWN_DISEASE_SPECIFIC:
                continue
            for number, code in self._code_lines(path):
                if self.BANNED.search(code):
                    offenders.append(f"{path.name}:{number}: {code[:80]}")
        assert not offenders, "disease-specific logic found:\n" + "\n".join(offenders)

    def test_allowlist_is_empty(self) -> None:
        # The generalisation goal: no module needs an exemption.
        assert self.KNOWN_DISEASE_SPECIFIC == {}

    def test_known_disease_specific_modules_are_not_growing(self) -> None:
        # Guards the allowlist: a module that no longer needs an exemption
        # should lose it, so the debt can only shrink.
        still_needed = set()
        for name in self.KNOWN_DISEASE_SPECIFIC:
            matches = list((ROOT / "backend/src/atlas").rglob(name))
            if not matches:
                continue
            if any(self.BANNED.search(code) for _n, code in self._code_lines(matches[0])):
                still_needed.add(name)
        assert still_needed == set(self.KNOWN_DISEASE_SPECIFIC), (
            "allowlist is stale; remove entries that no longer contain "
            f"disease-specific code: {set(self.KNOWN_DISEASE_SPECIFIC) - still_needed}"
        )


class TestCrossDiseaseSynthesis:
    """A gap must rest on evidence; an experiment must be able to fail."""

    @staticmethod
    def _inputs(**overrides):
        from atlas.domain.cross_disease import (
            MechanisticBridge,
            RelationshipClass,
            ValidatedRelationship,
        )
        from atlas.services.cross_disease_synthesis import SynthesisInputs

        relationship = overrides.pop("relationship", None) or ValidatedRelationship(
            relationship_id="r:test", disease_a="a", disease_b="b",
            relationship_class=RelationshipClass.SHARED_DOWNSTREAM_MECHANISM,
            mechanistic_statement="linked", evidence_ids=("PMID:1", "PMID:2"),
            # A gap now requires the evidence-derived bridge, so the fixture
            # supplies one rather than the test being relaxed.
            mechanistic_bridge=MechanisticBridge(
                bridge_id="bridge:fixture", terms=("a specific axis",),
                derived_from_evidence_ids=("PMID:1", "PMID:2"),
                statement="derived from evidence", derivation_method="fixture",
                distinct_from_retrieval_features=("a shared process",),
            ),
            source_version="v1",
        )
        from datetime import UTC, datetime

        from atlas.domain.gaps import CoverageStatus, SearchCoverage, SearchSourceCoverage

        coverage = SearchCoverage(
            coverage_id="coverage:test",
            sources=(
                SearchSourceCoverage(
                    source="PubMed", status=CoverageStatus.CHECKED,
                    queries=("test query",), result_count=2,
                    checked_at=datetime.now(UTC),
                ),
            ),
            search_started_at=datetime.now(UTC),
            scope="test",
            language_limitations=(),
            geographic_limitations=(),
            interpretation_caveat="test",
        )
        base = dict(
            relationship=relationship, comparison=None, coverage=coverage,
            disease_a_name="Disease A", disease_b_name="Disease B",
            shared_process_label="a shared process",
            shared_readout="a functional assay",
            model_system="cellular models",
            supporting_evidence=("PMID:1", "PMID:2"),
            contradicting_evidence=(),
        )
        base.update(overrides)
        return SynthesisInputs(**base)

    def test_gap_requires_a_mechanistic_relationship(self) -> None:
        from atlas.domain.cross_disease import RelationshipClass, ValidatedRelationship
        from atlas.services.cross_disease_synthesis import build_cross_disease_gap

        weak = ValidatedRelationship(
            relationship_id="r:weak", disease_a="a", disease_b="b",
            relationship_class=RelationshipClass.SHARED_PHENOTYPE_ONLY,
            mechanistic_statement="symptoms only", source_version="v1",
        )
        with pytest.raises(ValueError, match="no open"):
            build_cross_disease_gap(self._inputs(relationship=weak))

    def test_gap_requires_evidence_not_annotation(self) -> None:
        from atlas.domain.cross_disease import RelationshipClass, ValidatedRelationship

        # A mechanistic class cannot exist without evidence, so this constructs
        # the nearest thing: a class that is gap-worthy with empty evidence.
        with pytest.raises(ValueError):
            ValidatedRelationship(
                relationship_id="r:none", disease_a="a", disease_b="b",
                relationship_class=RelationshipClass.SHARED_PATHWAY,
                mechanistic_statement="", source_version="v1",
            )

    def test_generated_experiment_is_falsifiable(self) -> None:
        from atlas.services.cross_disease_synthesis import (
            build_cross_disease_experiment,
            build_cross_disease_gap,
        )

        inputs = self._inputs()
        gap = build_cross_disease_gap(inputs)
        experiment = build_cross_disease_experiment(gap, inputs)
        assert experiment.expected_result_if_refuted
        assert (
            experiment.expected_result_if_refuted
            != experiment.expected_result_if_supported
        )
        assert experiment.human_review_required

    def test_experiment_without_refutation_is_rejected(self) -> None:
        from atlas.services.cross_disease_synthesis import (
            NotFalsifiable,
            assert_falsifiable,
            build_cross_disease_experiment,
            build_cross_disease_gap,
        )

        inputs = self._inputs()
        gap = build_cross_disease_gap(inputs)
        good = build_cross_disease_experiment(gap, inputs)
        # An experiment that cannot fail must raise, not warn.
        with pytest.raises(NotFalsifiable, match="cannot fail"):
            assert_falsifiable(good.model_copy(update={"expected_result_if_refuted": ""}))

    def test_indistinguishable_outcomes_are_rejected(self) -> None:
        from atlas.services.cross_disease_synthesis import (
            NotFalsifiable,
            assert_falsifiable,
            build_cross_disease_experiment,
            build_cross_disease_gap,
        )

        inputs = self._inputs()
        gap = build_cross_disease_gap(inputs)
        good = build_cross_disease_experiment(gap, inputs)
        same = good.model_copy(
            update={"expected_result_if_refuted": good.expected_result_if_supported}
        )
        with pytest.raises(NotFalsifiable, match="distinguish"):
            assert_falsifiable(same)

    def test_experiment_declares_its_own_requirements(self) -> None:
        # The requirement extractor reads what the experiment states, so a
        # proposal that declares nothing yields no capabilities and the action
        # pathway silently produces nothing.
        from atlas.services.cross_disease_synthesis import (
            build_cross_disease_experiment,
            build_cross_disease_gap,
        )
        from atlas.services.requirement_extraction import extract_experiment_requirements

        inputs = self._inputs()
        gap = build_cross_disease_gap(inputs)
        experiment = build_cross_disease_experiment(gap, inputs)
        capabilities, assets = extract_experiment_requirements(experiment)
        assert capabilities
        assert assets


class TestLayeredIdentity:
    def test_contained_gene_set_yields_a_scoped_same_entity_verdict(self) -> None:
        from atlas.services.disease_identity import IdentitySignals, scoped_identities

        narrow = {"disease_name": "Narrow", "disease_id": "n"}
        broad = {"disease_name": "Broad", "disease_id": "b"}
        signals = IdentitySignals(
            shared_genes=("HGNC:1",), only_genes_a=(), only_genes_b=("HGNC:2", "HGNC:3"),
            phenotype_overlap=0.4, shared_phenotype_count=4,
            name_core_match=False, same_mondo=False,
        )
        scoped = scoped_identities(narrow, broad, signals)
        assert len(scoped) == 1
        assert scoped[0].relation is IdentityRelation.ALLELIC_SPECTRUM
        assert "not an independent" in scoped[0].rationale

    def test_scoped_same_entity_blocks_independent_discovery(self) -> None:
        from atlas.domain.cross_disease import RelationshipClass, ValidatedRelationship

        relationship = ValidatedRelationship(
            relationship_id="r:scoped", disease_a="a", disease_b="b",
            relationship_class=RelationshipClass.SHARED_DOWNSTREAM_MECHANISM,
            mechanistic_statement="linked", evidence_ids=("PMID:1",),
            identity_relation=IdentityRelation.PARTIALLY_OVERLAPPING_ENTITY,
            identity_has_same_entity_scope=True,
            source_version="v1",
        )
        assert not relationship.is_independent_discovery

    def test_identical_gene_sets_produce_no_scope(self) -> None:
        from atlas.services.disease_identity import IdentitySignals, scoped_identities

        signals = IdentitySignals(
            shared_genes=("HGNC:1",), only_genes_a=(), only_genes_b=(),
            phenotype_overlap=0.8, shared_phenotype_count=8,
            name_core_match=True, same_mondo=False,
        )
        assert scoped_identities({"disease_name": "A"}, {"disease_name": "B"}, signals) == ()


class TestGapDerivesFromBridgeNotRetrieval:
    """The scientific-integrity rule this phase exists to enforce.

    A knowledge gap must be built from the mechanistic explanation the evidence
    supports, never from the annotation that happened to retrieve the pair.
    Testing the retrieval feature measures a process both diseases touch while
    missing the step where they actually meet, and a null result would then be
    uninterpretable. The assertions are structural: no biology is named.
    """

    FLAGSHIP = ROOT / "data/flagship/flagship_journey.json"

    @staticmethod
    def _bridge(terms, evidence=("PMID:1", "PMID:2"), retrieval=("broad term",)):
        from atlas.domain.cross_disease import MechanisticBridge

        return MechanisticBridge(
            bridge_id="bridge:test", terms=tuple(terms),
            derived_from_evidence_ids=tuple(evidence),
            statement="derived", derivation_method="test",
            distinct_from_retrieval_features=tuple(retrieval),
        )

    def test_bridge_cannot_exist_without_evidence(self) -> None:
        # A bridge with no evidence is a retrieval reason wearing another name.
        with pytest.raises(ValueError, match="derived from evidence"):
            self._bridge(("some axis",), evidence=())

    def test_gap_refuses_to_build_without_a_bridge(self) -> None:
        from atlas.domain.cross_disease import RelationshipClass, ValidatedRelationship
        from atlas.services.cross_disease_synthesis import build_cross_disease_gap

        relationship = ValidatedRelationship(
            relationship_id="r:nobridge", disease_a="a", disease_b="b",
            relationship_class=RelationshipClass.SHARED_DOWNSTREAM_MECHANISM,
            mechanistic_statement="linked", evidence_ids=("PMID:1",),
            source_version="v1",
        )
        inputs = TestCrossDiseaseSynthesis._inputs(relationship=relationship)
        with pytest.raises(ValueError, match="mechanistic bridge"):
            build_cross_disease_gap(inputs)

    def test_gap_question_uses_the_bridge_not_the_retrieval_feature(self) -> None:
        from atlas.domain.cross_disease import RelationshipClass, ValidatedRelationship
        from atlas.services.cross_disease_synthesis import build_cross_disease_gap

        relationship = ValidatedRelationship(
            relationship_id="r:bridged", disease_a="a", disease_b="b",
            relationship_class=RelationshipClass.SHARED_DOWNSTREAM_MECHANISM,
            mechanistic_statement="linked", evidence_ids=("PMID:1", "PMID:2"),
            mechanistic_bridge=self._bridge(("narrow specific axis",)),
            source_version="v1",
        )
        inputs = TestCrossDiseaseSynthesis._inputs(
            relationship=relationship, shared_process_label="broad term"
        )
        gap = build_cross_disease_gap(inputs)
        assert "narrow specific axis" in gap.question
        # The retrieval feature may be mentioned as context, but the question
        # must not be asked about it.
        assert "broad term" not in gap.question

    def test_experiment_measures_the_bridge(self) -> None:
        from atlas.domain.cross_disease import RelationshipClass, ValidatedRelationship
        from atlas.services.cross_disease_synthesis import (
            build_cross_disease_experiment,
            build_cross_disease_gap,
        )

        relationship = ValidatedRelationship(
            relationship_id="r:measure", disease_a="a", disease_b="b",
            relationship_class=RelationshipClass.SHARED_DOWNSTREAM_MECHANISM,
            mechanistic_statement="linked", evidence_ids=("PMID:1", "PMID:2"),
            mechanistic_bridge=self._bridge(("narrow specific axis",)),
            source_version="v1",
        )
        inputs = TestCrossDiseaseSynthesis._inputs(
            relationship=relationship, shared_process_label="broad term"
        )
        experiment = build_cross_disease_experiment(
            build_cross_disease_gap(inputs), inputs
        )
        assert "narrow specific axis" in experiment.readouts[0]
        assert "narrow specific axis" in experiment.primary_endpoint

    def test_a_different_bridge_is_a_different_gap(self) -> None:
        # Reusing a gap id across different mechanistic explanations would hide
        # that the question changed.
        from atlas.domain.cross_disease import RelationshipClass, ValidatedRelationship
        from atlas.services.cross_disease_synthesis import build_cross_disease_gap

        def gap_for(terms):
            relationship = ValidatedRelationship(
                relationship_id="r:same", disease_a="a", disease_b="b",
                relationship_class=RelationshipClass.SHARED_DOWNSTREAM_MECHANISM,
                mechanistic_statement="linked", evidence_ids=("PMID:1", "PMID:2"),
                mechanistic_bridge=self._bridge(terms), source_version="v1",
            )
            return build_cross_disease_gap(
                TestCrossDiseaseSynthesis._inputs(relationship=relationship)
            )

        assert gap_for(("axis one",)).gap_id != gap_for(("axis two",)).gap_id

    @pytest.mark.skipif(not FLAGSHIP.exists(), reason="flagship not generated")
    def test_flagship_gap_has_not_regressed_to_the_retrieval_feature(self) -> None:
        # Regression guard on the real artifact: the published flagship question
        # must be about the validated bridge, not the annotation that found it.
        payload = json.loads(self.FLAGSHIP.read_text())
        retrieval = payload["retrieval_level_feature"]
        bridge = payload["validated_mechanistic_bridge"]
        question = payload["knowledge_gap"]["question"]

        from atlas.domain.cross_disease import MechanisticBridge

        assert bridge is not None, "flagship lost its mechanistic bridge"
        # Validate rather than read raw keys: computed properties are not in the
        # serialised form, and the invariant belongs to the model.
        model = MechanisticBridge.model_validate(bridge)
        assert model.derived_from_evidence_ids, "bridge not evidence-derived"
        assert model.is_narrower_than_retrieval, (
            "bridge collapsed to the retrieval feature"
        )
        assert retrieval.casefold() not in question.casefold(), (
            f"flagship gap regressed to asking about the retrieval feature "
            f"{retrieval!r}"
        )
        assert any(
            term.casefold() in question.casefold() for term in bridge["terms"]
        ), "flagship gap does not reference the validated bridge"


class TestBridgeVersioningAndDisplayLabels:
    """Refinement must supersede, never overwrite; labels must not conclude."""

    @staticmethod
    def _bridge(**kw):
        from atlas.domain.cross_disease import MechanisticBridge

        base = dict(
            bridge_id="bridge:v1", terms=("axis one",),
            derived_from_evidence_ids=("PMID:1",), statement="s",
            derivation_method="m",
        )
        base.update(kw)
        return MechanisticBridge(**base)

    def test_bridge_versions_are_immutable(self) -> None:
        # Frozen: a refinement cannot edit the version that preceded it.
        from pydantic import ValidationError

        v1 = self._bridge()
        with pytest.raises(ValidationError):
            v1.terms = ("something else",)  # type: ignore[misc]

    def test_refinement_names_its_parent(self) -> None:
        v2 = self._bridge(
            bridge_id="bridge:v2", version=2, supersedes_bridge_id="bridge:v1",
            terms=("axis one", "axis two"), refinement_reason="new primary finding",
        )
        assert v2.supersedes_bridge_id == "bridge:v1"
        assert v2.version > 1
        assert v2.refinement_reason

    def test_refined_bridge_still_requires_evidence(self) -> None:
        with pytest.raises(ValueError, match="derived from evidence"):
            self._bridge(bridge_id="b:v2", version=2, derived_from_evidence_ids=())

    def test_primary_terms_exclude_background_supported_ones(self) -> None:
        from atlas.domain.cross_disease import BridgeTermProvenance

        bridge = self._bridge(
            terms=("axis one", "axis two"),
            term_provenance=(
                BridgeTermProvenance(
                    term="axis one", source_id="PMID:1", span="we demonstrate",
                    annotation_type="Gene Function",
                    finding_role="PRIMARY_EXPERIMENTAL_RESULT", section="Abstract",
                ),
                BridgeTermProvenance(
                    term="axis two", source_id="PMID:1", span="previously shown",
                    annotation_type="Gene Function",
                    finding_role="BACKGROUND_STATEMENT", section="Abstract",
                ),
            ),
        )
        assert bridge.primary_terms == ("axis one",)

    def test_display_label_cannot_add_entities(self) -> None:
        from atlas.domain.cross_disease import validate_display_label

        with pytest.raises(ValueError, match="introduces"):
            validate_display_label("axis one and some other factor", ("axis one",))

    def test_display_label_cannot_escalate_causality(self) -> None:
        from atlas.domain.cross_disease import validate_display_label

        with pytest.raises(ValueError, match="asserts"):
            validate_display_label("axis one causes the disease", ("axis one",))

    def test_display_label_may_simplify_wording(self) -> None:
        from atlas.domain.cross_disease import validate_display_label

        validate_display_label(
            "chaperone and ligase associated biology", ("chaperone", "ligase")
        )

    def test_override_label_is_validated_on_use(self) -> None:
        bad = self._bridge(display_label_override="axis one proves equivalence")
        with pytest.raises(ValueError):
            _ = bad.display_label


class TestPrimaryReadoutRules:
    def test_secondary_readouts_cannot_carry_falsifiability(self) -> None:
        from atlas.services.cross_disease_synthesis import (
            NotFalsifiable,
            assert_falsifiable,
            build_cross_disease_experiment,
            build_cross_disease_gap,
        )

        inputs = TestCrossDiseaseSynthesis._inputs()
        gap = build_cross_disease_gap(inputs)
        experiment = build_cross_disease_experiment(gap, inputs)
        assert experiment.primary_readout
        assert experiment.secondary_readouts
        # Emptying the primary readout must fail even though secondaries remain.
        with pytest.raises(NotFalsifiable, match="primary readout"):
            assert_falsifiable(experiment.model_copy(update={"primary_readout": "  "}))

    def test_primary_readout_measures_the_bridge(self) -> None:
        from atlas.services.cross_disease_synthesis import (
            build_cross_disease_experiment,
            build_cross_disease_gap,
        )

        inputs = TestCrossDiseaseSynthesis._inputs()
        gap = build_cross_disease_gap(inputs)
        experiment = build_cross_disease_experiment(gap, inputs)
        bridge = inputs.relationship.mechanistic_bridge
        assert bridge is not None
        assert any(
            term.casefold() in (experiment.primary_readout or "").casefold()
            for term in bridge.terms
        )
