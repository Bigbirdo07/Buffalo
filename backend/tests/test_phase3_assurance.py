"""Cross-artifact assurance tests for the completed Phase 3 chain."""

from __future__ import annotations

import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from scripts.build_phase3_assurance import (
    VOLATILE_KEYS,
    canonicalize,
    verify_snapshot_body,
)

ROOT = Path(__file__).parents[2]
RUN_DIR = ROOT / "data" / "refinement" / "scar16_stub1_e3"
LINEAGE = RUN_DIR / "claim_lineage.json"
MANIFEST = RUN_DIR / "reproducibility_manifest.json"


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())


class Phase3AssuranceTests(unittest.TestCase):
    def setUp(self) -> None:
        if not LINEAGE.exists() or not MANIFEST.exists():
            self.fail("run scripts/build_phase3_assurance.py to generate assurance artifacts")
        self.refinement = load(RUN_DIR / "edge_refinement.json")
        self.gap = load(RUN_DIR / "knowledge_gap.json")
        self.experiment = load(RUN_DIR / "experiment_proposal.json")
        self.lineage = load(LINEAGE)
        self.manifest = load(MANIFEST)

    def test_lineage_connects_upstream_claim_to_atomic_claims(self) -> None:
        upstream = self.lineage["upstream"]
        self.assertEqual(upstream["claim_id"], self.refinement["upstream_claim"]["claim_id"])
        self.assertEqual(upstream["edge_id"], self.refinement["upstream_edge_id"])
        for atomic in self.lineage["atomic_claims"]:
            self.assertEqual(atomic["derived_from_claim_ids"], [upstream["claim_id"]])

    def test_every_precise_evidence_reference_resolves(self) -> None:
        observations = {
            item["observation_id"]: item for item in self.lineage["observations"]
        }
        for atomic in self.lineage["atomic_claims"]:
            for references in atomic["evidence_by_role"].values():
                for reference in references:
                    evidence_id, observation_id = reference.rsplit("#", 1)
                    self.assertIn(observation_id, observations)
                    self.assertEqual(observations[observation_id]["evidence_id"], evidence_id)

    def test_one_publication_can_have_distinguishable_findings(self) -> None:
        by_evidence: dict[str, set[str]] = {}
        for item in self.lineage["observations"]:
            by_evidence.setdefault(item["evidence_id"], set()).add(item["observation_id"])
        repeated = [ids for ids in by_evidence.values() if len(ids) > 1]
        self.assertTrue(repeated)
        self.assertTrue(any({"o02", "o04"} <= ids for ids in repeated))

    def test_readout_and_domain_decisions_are_preserved(self) -> None:
        plan = load(RUN_DIR / "observation_plan.json")
        self.assertNotIn("self_ubiquitination", plan["readout_family"])
        observations = {item["observation_id"]: item for item in self.lineage["observations"]}
        self.assertEqual(observations["o07"]["effect"], "processivity_defect")
        self.assertEqual(observations["o09"]["effect"], "processivity_defect")
        gap_text = json.dumps(self.gap)
        self.assertIn("inter-domain/linker-region", gap_text)
        self.assertNotIn("inter-domain (coiled-coil region)", gap_text)

    def test_gap_and_experiment_links_close_the_chain(self) -> None:
        gap_link = self.lineage["knowledge_gap"]
        experiment_link = self.lineage["experiment_proposal"]
        self.assertEqual(gap_link["gap_id"], self.gap["gap_id"])
        self.assertEqual(experiment_link["experiment_id"], self.experiment["experiment_id"])
        self.assertEqual(experiment_link["knowledge_gap_id"], gap_link["gap_id"])
        self.assertTrue(experiment_link["human_review_required"])

    def test_human_review_remains_pending(self) -> None:
        self.assertEqual(self.lineage["human_review"]["status"], "PENDING")
        self.assertEqual(self.manifest["human_review"]["status"], "PENDING")

    def test_manifest_artifact_hashes_match_current_bytes(self) -> None:
        for relative, expected in self.manifest["artifact_sha256"].items():
            actual = sha256((ROOT / relative).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, relative)

    def test_manifest_implementation_hashes_match_current_bytes(self) -> None:
        for relative, expected in self.manifest["implementation_sha256"].items():
            actual = sha256((ROOT / relative).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, relative)

    def test_manifest_source_and_snapshot_hashes_match(self) -> None:
        source = self.manifest["source"]
        self.assertEqual(sha256((ROOT / source["file"]).read_bytes()).hexdigest(), source["sha256"])
        snapshots = self.manifest["cached_snapshots"]
        self.assertGreater(snapshots["count"], 0)
        self.assertTrue(snapshots["all_hashes_match"])
        for item in snapshots["records"]:
            self.assertTrue(item["matches"])
            self.assertEqual(item["recorded_sha256"], item["actual_sha256"])

    def test_manifest_records_successful_offline_replay(self) -> None:
        replay = self.manifest["offline_reproduction"]
        self.assertEqual(replay["status"], "PASS")
        self.assertFalse(replay["network_required"])
        self.assertEqual(set(replay["canonicalization"]["excluded_keys"]), VOLATILE_KEYS)
        for result in replay["results"].values():
            self.assertTrue(result["matches"])

    def test_canonicalization_changes_only_declared_volatile_fields(self) -> None:
        value = {"status": "SUPPORTED", "created_at": "one", "nested": {"checked_at": "two"}}
        self.assertEqual(canonicalize(value), {"nested": {}, "status": "SUPPORTED"})
        self.assertNotIn("status", VOLATILE_KEYS)

    def test_changed_cached_source_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            meta = Path(temp_name) / "snapshot.json"
            body = meta.with_suffix(".body")
            original = b"original source bytes"
            meta.write_text(json.dumps({"sha256": sha256(original).hexdigest()}))
            body.write_bytes(b"tampered source bytes")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify_snapshot_body(meta)


if __name__ == "__main__":
    unittest.main()
