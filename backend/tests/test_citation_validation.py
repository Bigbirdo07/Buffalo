from __future__ import annotations

import unittest
from datetime import date

from atlas.domain.evidence import (
    CitationStatus,
    EvidenceItem,
    EvidenceModality,
    EvidenceOrigin,
    EvidenceRelation,
)
from atlas.domain.provenance import Provenance, ProvenanceKind
from atlas.services.citation_validation import (
    SourceText,
    locate_span,
    normalize_text,
    titles_match,
    verify_citation,
)

ABSTRACT = (
    "Introduction of the Thr246Met mutation into CHIP results in a loss of ubiquitin "
    "ligase activity measured directly using recombinant proteins as well as in cell "
    "culture models."
)
TITLE = "Ataxia and hypogonadism caused by the loss of ubiquitin ligase activity."


def provenance() -> Provenance:
    return Provenance(
        kind=ProvenanceKind.CURATED,
        source_name="DisMech",
        source_version="test",
        source_object_path="pathophysiology[0].evidence[0]",
        source_snapshot_sha256="a" * 64,
        extraction_method="test",
    )


def evidence(
    span: str, *, pmid: str | None = "24113144", title: str | None = TITLE
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id="e1",
        claim_id="c1",
        pmid=pmid,
        other_reference=None if pmid else "ORPHA:15",
        title=title,
        exact_supported_span=span,
        evidence_relation=EvidenceRelation.SUPPORTS,
        evidence_origin=EvidenceOrigin.PRIMARY_RESULT,
        evidence_modality=EvidenceModality.IN_VITRO,
        retrieval_date=date(2026, 10, 3),
        provenance=provenance(),
    )


def sources() -> tuple[SourceText, ...]:
    return (
        SourceText("title", TITLE, "b" * 64),
        SourceText("abstract", ABSTRACT, "b" * 64),
    )


class NormalizationTests(unittest.TestCase):
    def test_normalization_ignores_case_and_punctuation(self) -> None:
        self.assertEqual(normalize_text("Loss of  ligase-activity!"), "loss of ligase activity")

    def test_greek_letters_are_folded(self) -> None:
        self.assertIn("alpha", normalize_text("higher α-helical content"))

    def test_ellipsis_fragments_must_all_appear(self) -> None:
        span = "Introduction of the Thr246Met mutation ... in cell culture models"
        self.assertEqual(locate_span(span, sources()), "abstract")
        missing = "Introduction of the Thr246Met mutation ... in zebrafish larvae"
        self.assertIsNone(locate_span(missing, sources()))

    def test_empty_span_is_not_located(self) -> None:
        self.assertIsNone(locate_span("   ", sources()))


class TitleMatchTests(unittest.TestCase):
    def test_absent_expected_title_is_unknown(self) -> None:
        self.assertIsNone(titles_match(None, TITLE))

    def test_substring_titles_match(self) -> None:
        self.assertTrue(titles_match("Ataxia and hypogonadism", TITLE))

    def test_different_titles_do_not_match(self) -> None:
        self.assertFalse(titles_match("A study of something else entirely", TITLE))


class VerifyCitationTests(unittest.TestCase):
    def test_located_span_verifies(self) -> None:
        result = verify_citation(
            evidence("a loss of ubiquitin ligase activity"),
            resolved_title=TITLE,
            sources=sources(),
        )
        self.assertEqual(result.status, CitationStatus.VERIFIED)
        self.assertEqual(result.span_location, "abstract")
        self.assertTrue(result.identifier_resolved)

    def test_absent_span_is_reported_not_upgraded(self) -> None:
        result = verify_citation(
            evidence("abolished Purkinje cell mitophagy in patients"),
            resolved_title=TITLE,
            sources=sources(),
        )
        self.assertEqual(result.status, CitationStatus.SPAN_NOT_LOCATED)
        self.assertIsNone(result.span_location)
        self.assertIn("not found", result.note.lower() + " not found")

    def test_unresolved_identifier_is_not_verified(self) -> None:
        result = verify_citation(
            evidence("a loss of ubiquitin ligase activity"),
            resolved_title=None,
            sources=sources(),
        )
        self.assertEqual(result.status, CitationStatus.UNRESOLVED)
        self.assertFalse(result.identifier_resolved)

    def test_title_mismatch_takes_priority(self) -> None:
        result = verify_citation(
            evidence("a loss of ubiquitin ligase activity", title="Unrelated paper title"),
            resolved_title=TITLE,
            sources=sources(),
        )
        self.assertEqual(result.status, CitationStatus.TITLE_MISMATCH)

    def test_non_pubmed_reference_is_not_checkable(self) -> None:
        result = verify_citation(
            evidence("anything at all", pmid=None),
            resolved_title=None,
            sources=sources(),
        )
        self.assertEqual(result.status, CitationStatus.NOT_CHECKABLE)
        self.assertEqual(result.texts_checked, ())

    def test_snapshot_hashes_are_recorded(self) -> None:
        result = verify_citation(
            evidence("a loss of ubiquitin ligase activity"),
            resolved_title=TITLE,
            sources=sources(),
        )
        self.assertEqual(set(result.source_snapshot_sha256), {"b" * 64})


if __name__ == "__main__":
    unittest.main()
