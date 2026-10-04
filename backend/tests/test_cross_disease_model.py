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
    DiseaseIdentityRelationship,
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

    # Modules that still carry disease-specific logic, with the reason. These
    # are Phase 4 action-engine code written for a single worked example and not
    # yet generalised. Listing them makes the debt visible and bounded: a new
    # module cannot quietly join this list without a deliberate edit.
    KNOWN_DISEASE_SPECIFIC = {
        "capability_discovery.py": (
            "Phase 4 search queries written for one worked disease; generalising "
            "them is the cross-disease action-engine task."
        ),
        "requirement_extraction.py": (
            "One capability label carries a worked-example gene name."
        ),
    }

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
