"""Accuracy tests for the generated viewer.

A demo that overstates is worse than no demo, so these assert that the page's
claims match the artifacts and that its hedges are present. They check content,
not styling.
"""

from __future__ import annotations

import html
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[2]
PAGE = ROOT / "data" / "viewer" / "index.html"
REFINEMENTS = {
    "SCAR16": ROOT / "data/refinement/scar16_stub1_e3",
    "SCAR20": ROOT / "data/refinement/scar20_snx14_autophagy",
}
ACTION = ROOT / "data/action/scar16_stub1_e3"


def _load(path: Path):  # type: ignore[no-untyped-def]
    return json.loads(path.read_text())


class ViewerAccuracyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = PAGE.read_text()
        # Line wrapping in the generator splits sentences across newlines, so
        # prose assertions run against a whitespace-normalized copy.
        cls.flat = re.sub(r"\s+", " ", cls.html)

    def assertInPage(self, needle: str, label: str = "") -> None:
        """Assert without dumping the whole 80KB page into the failure."""
        if re.sub(r"\s+", " ", needle) not in self.flat:
            self.fail(f"not found in page: {label or needle[:70]!r}")

    def test_every_atomic_claim_statement_appears(self) -> None:
        for run_dir in REFINEMENTS.values():
            refinement = _load(run_dir / "edge_refinement.json")
            for atomic in refinement["atomic"]:
                statement = atomic["claim"]["normalized_statement"]
                self.assertInPage(html.escape(statement, quote=True), statement[:60])

    def test_every_evidence_span_appears_verbatim(self) -> None:
        """The quoted passage shown must be the one in the artifact."""
        for run_dir in REFINEMENTS.values():
            refinement = _load(run_dir / "edge_refinement.json")
            used = {r["source_id"] for r in refinement["reviews"]}
            for observation in refinement["observations"]:
                if observation["observation_id"] not in used:
                    continue
                span = observation["support_span"].strip()
                # Escape exactly as the generator does, or an apostrophe
                # (&#x27;) makes a correct page look wrong.
                needle = html.escape(span[:70], quote=True)
                self.assertInPage(needle, observation["observation_id"])

    def test_edge_verdicts_match_the_artifacts(self) -> None:
        labels = {
            "SUPPORTED": "Supported",
            "PARTIALLY_SUPPORTED": "Partly supported",
            "CONTEXT_DEPENDENT": "Depends on context",
            "INSUFFICIENT_EVIDENCE": "Not enough evidence",
            "CONTRADICTED": "Contradicted",
        }
        for run_dir in REFINEMENTS.values():
            refinement = _load(run_dir / "edge_refinement.json")
            self.assertInPage(labels[refinement["edge_status"]])
            self.assertInPage(f'rule {refinement["edge_rule_applied"]}')

    def test_no_numeric_confidence_is_shown(self) -> None:
        """The engine computes no confidence value, so none may be displayed.

        The page's own disclaimer naming confidence scores is required, so only
        numeric forms are treated as violations.
        """
        for pattern in (
            r"\d{1,3}\s?%\s*(confiden|certain|probab)",
            r"confidence[^.]{0,20}[:=]\s*\d",
            r"\bscore\s*[:=]\s*\d",
        ):
            self.assertIsNone(
                re.search(pattern, self.flat, re.IGNORECASE), f"matched {pattern}"
            )
        self.assertInPage("No confidence scores")

    def test_corpus_figures_match_the_audit(self) -> None:
        totals = _load(ROOT / "data/audit/corpus_audit.json")["totals"]
        self.assertInPage(f'{totals["files_imported"]:,}')
        self.assertInPage(f'{totals["evidence"]:,}')
        self.assertEqual(totals["undeclared_paths"], 0)
        self.assertInPage("silently dropped fields")

    def test_collaboration_status_is_not_softened(self) -> None:
        collaboration = _load(ACTION / "collaboration_opportunity.json")
        self.assertEqual(collaboration["status"], "MISSING_CAPABILITY")
        self.assertInPage("MISSING_CAPABILITY")
        caps = {
            c["capability_id"]: c["canonical_name"]
            for c in _load(ACTION / "required_capabilities.json")
        }
        for missing in collaboration["missing_capabilities"]:
            self.assertInPage(caps[missing])

    def test_no_asset_is_presented_as_validated(self) -> None:
        for asset in _load(ACTION / "research_assets.json"):
            self.assertEqual(asset["reuse_status"], "REQUIRES_VALIDATION")
        self.assertInPage("REQUIRES_VALIDATION")
        self.assertNotIn("VALIDATED_FOR_TARGET_CONTEXT", self.flat)

    def test_failed_and_unattempted_sources_are_shown(self) -> None:
        coverage = _load(ACTION / "search_coverage.json")
        for source in coverage["sources"]:
            if source["status"] in {"FAILED", "NOT_STARTED"}:
                self.assertInPage(source["source"], source["source"])
        self.assertInPage("FAILED")
        self.assertInPage("NOT_STARTED")

    def test_required_hedges_are_present(self) -> None:
        for phrase in (
            "not a language model",
            "have not been reviewed",
            "least validated step",
            "has confirmed any capability",
            "Two diseases is not a validated sample",
        ):
            self.assertInPage(phrase, phrase)

    def test_experiment_label_is_exact(self) -> None:
        experiment = _load(REFINEMENTS["SCAR16"] / "experiment_proposal.json")
        self.assertEqual(
            experiment["label"], "Research proposal requiring expert review."
        )
        self.assertInPage(experiment["label"])

    def test_scar20_absence_of_a_gap_is_stated_not_hidden(self) -> None:
        self.assertFalse((REFINEMENTS["SCAR20"] / "knowledge_gap.json").exists())
        self.assertInPage("Not generated for this disease yet")

    def test_citation_tiers_are_explained_and_counted(self) -> None:
        counts: dict[str, int] = {}
        for run_dir in REFINEMENTS.values():
            refinement = _load(run_dir / "edge_refinement.json")
            for check in refinement["citation_checks"]:
                counts[check["status"]] = counts.get(check["status"], 0) + 1
        self.assertIn("UPSTREAM_ATTESTED", counts)
        self.assertInPage("quote found in the paper")
        self.assertInPage("text not readable")

    def test_page_is_self_contained(self) -> None:
        """No server and no data fetch: it must open from the filesystem."""
        self.assertNotIn("fetch(", self.html)
        self.assertNotIn("XMLHttpRequest", self.html)
        external = re.findall(r'src="https?://([^/"]+)', self.html)
        self.assertEqual(external, [], f"unexpected external scripts: {external}")

    def test_theme_tokens_are_defined_for_all_three_states(self) -> None:
        self.assertInPage("prefers-color-scheme: dark")
        self.assertInPage(':root[data-theme="dark"]')
        self.assertInPage(':root:not([data-theme="light"])')
        self.assertRegex(self.html, r"body\s*\{[^}]*background:\s*var\(--bg\)")


if __name__ == "__main__":
    unittest.main()
