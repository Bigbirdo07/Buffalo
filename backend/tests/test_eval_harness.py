"""Tests for the blind adjudication harness.

The harness exists to measure the engine rather than assert it is right, so the
properties that matter are that the blinding genuinely holds, that the answer key
is bound to the exact worksheet shown, and that status disagreement is reported
separately from extraction dispute.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).parents[2]
EVAL = ROOT / "data" / "eval" / "round-1"
STATUSES = (
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "CONTEXT_DEPENDENT",
    "INSUFFICIENT_EVIDENCE",
    "CONTRADICTED",
)


def _load(name: str):  # type: ignore[no-untyped-def]
    return json.loads((EVAL / name).read_text())


class WorksheetBlindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.worksheet = _load("worksheet.json")
        self.key = _load("answer_key.json")

    def test_no_engine_status_appears_in_any_item(self) -> None:
        payload = json.dumps(self.worksheet["items"])
        for status in STATUSES:
            self.assertNotIn(status, payload, f"{status} leaked into the worksheet items")

    def test_no_rule_or_rationale_leaks(self) -> None:
        payload = json.dumps(self.worksheet["items"])
        for forbidden in ("rule_applied", "engine_status", "engine_rationale"):
            self.assertNotIn(forbidden, payload)
        markdown = (EVAL / "worksheet.md").read_text()
        for forbidden in ("rule A", "rule E", "engine_rationale"):
            self.assertNotIn(forbidden, markdown)

    def test_critic_verdicts_are_withheld(self) -> None:
        """The reviewer must judge evidence, not review the critic's judgement."""
        payload = json.dumps(self.worksheet["items"])
        for forbidden in ("directness", "causal_support", "DIRECT", "QUALIFIES"):
            self.assertNotIn(forbidden, payload)

    def test_answer_key_is_bound_to_this_exact_worksheet(self) -> None:
        digest = sha256((EVAL / "worksheet.json").read_bytes()).hexdigest()
        self.assertEqual(digest, self.key["worksheet_sha256"])

    def test_every_item_has_an_answer_and_a_claim_to_judge(self) -> None:
        self.assertGreaterEqual(len(self.worksheet["items"]), 9)
        for item in self.worksheet["items"]:
            self.assertIn(item["item_id"], self.key["answers"])
            self.assertTrue(item["atomic_claim"].strip())
            self.assertTrue(item["scope"]["readout_family"])

    def test_evidence_rows_carry_what_is_needed_to_judge(self) -> None:
        rows = [row for item in self.worksheet["items"] for row in item["evidence"]]
        self.assertTrue(rows)
        for row in rows:
            self.assertTrue(row["span"].strip())
            self.assertTrue(row["citation_status"])
            self.assertTrue(row["origin"])
            self.assertTrue(row["effect_as_extracted"])

    def test_both_diseases_are_represented(self) -> None:
        diseases = {item["disease"] for item in self.worksheet["items"]}
        self.assertIn("SCAR16", diseases)
        self.assertIn("SCAR20", diseases)

    def test_order_is_shuffled_not_grouped_by_disease(self) -> None:
        order = [item["disease"] for item in self.worksheet["items"]]
        grouped = sorted(order, key=lambda value: value != order[0])
        self.assertNotEqual(order, grouped, "grouping by disease hints at structure")

    def test_response_template_covers_every_item_and_is_blank(self) -> None:
        template = _load("responses_template.json")
        ids = {row["item_id"] for row in template["responses"]}
        self.assertEqual(ids, {item["item_id"] for item in self.worksheet["items"]})
        for row in template["responses"]:
            self.assertEqual(row["reviewer_status"], "")
            self.assertFalse(row["extraction_disputed"])


class ScoringTests(unittest.TestCase):
    """The scorer is exercised against a synthetic adjudication."""

    @classmethod
    def setUpClass(cls) -> None:
        key = _load("answer_key.json")["answers"]
        template = _load("responses_template.json")
        template["reviewer_name"] = "unit-test"
        template["reviewer_role"] = "harness verification"
        flip = {
            "SUPPORTED": "INSUFFICIENT_EVIDENCE",
            "PARTIALLY_SUPPORTED": "SUPPORTED",
            "CONTEXT_DEPENDENT": "SUPPORTED",
            "INSUFFICIENT_EVIDENCE": "SUPPORTED",
        }
        for index, row in enumerate(template["responses"]):
            engine = key[row["item_id"]]["engine_status"]
            if index == 0:
                row["reviewer_status"] = flip.get(engine, "SUPPORTED")
                row["extraction_disputed"] = True
                row["note"] = "unit-test disagreement"
            else:
                row["reviewer_status"] = engine
        cls.path = EVAL / "responses.unittest.json"
        cls.path.write_text(json.dumps(template, indent=2) + "\n")
        subprocess.run(
            [
                sys.executable,
                "scripts/score_eval.py",
                "--responses",
                str(cls.path.relative_to(ROOT)),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            env={"PYTHONPATH": "backend/src", "PATH": "/usr/bin:/bin"},
        )
        cls.report = json.loads((EVAL / "agreement_report.unittest.json").read_text())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.path.unlink(missing_ok=True)
        (EVAL / "agreement_report.unittest.json").unlink(missing_ok=True)

    def test_agreement_rate_reflects_the_single_planted_disagreement(self) -> None:
        total = self.report["items_adjudicated"]
        self.assertEqual(self.report["status_agreement"]["disagreed"], 1)
        self.assertEqual(self.report["status_agreement"]["agreed"], total - 1)

    def test_disagreement_is_attributed_to_the_rule_that_fired(self) -> None:
        self.assertEqual(sum(self.report["disagreements_by_rule"].values()), 1)
        entry = self.report["disagreements"][0]
        self.assertTrue(entry["engine_rule"])
        self.assertNotEqual(entry["engine_status"], entry["reviewer_status"])
        self.assertEqual(entry["reviewer_note"], "unit-test disagreement")

    def test_extraction_dispute_is_tracked_separately_from_status(self) -> None:
        self.assertEqual(self.report["extraction_disputes"]["count"], 1)
        self.assertIn("extraction", self.report["extraction_disputes"]["note"].lower())

    def test_directional_bias_is_reported(self) -> None:
        bias = self.report["directional_bias"]
        self.assertIn("interpretation", bias)
        self.assertIn(
            "engine_stronger_than_reviewer",
            bias,
        )

    def test_small_sample_caveat_is_stated(self) -> None:
        joined = " ".join(self.report["caveats"]).lower()
        self.assertIn("confidence interval", joined)
        self.assertIn("one reviewer", joined)

    def test_report_name_derives_from_the_responses_file(self) -> None:
        """A trial run must not be able to clobber a real adjudication."""
        self.assertTrue((EVAL / "agreement_report.unittest.json").exists())
        self.assertFalse(
            (EVAL / "agreement_report.json").exists(),
            "scoring a named responses file must not write the canonical report",
        )


if __name__ == "__main__":
    unittest.main()
