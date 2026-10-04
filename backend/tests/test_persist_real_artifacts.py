"""Persistence checks over the real generated artifacts.

Runs against a temporary SQLite database so no server is required. The same
assertions hold for Postgres, which is the intended canonical store; see
scripts/persist_artifacts.py --database-url.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from atlas.domain.gaps import KnowledgeGap
from atlas.persistence.database import create_engine_for_url, create_schema
from atlas.persistence.repository import AtlasRepository

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from persist_artifacts import (  # noqa: E402
    ACTION,
    REFINEMENT,
    SOURCE_VERSION,
    _load_models,
)


class RealArtifactPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        url = f"sqlite+pysqlite:///{Path(self._temp.name) / 'atlas.sqlite3'}"
        engine = create_engine_for_url(url)
        create_schema(engine)
        self.repository = AtlasRepository(engine)
        self.models = _load_models()

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_every_real_artifact_round_trips_losslessly(self) -> None:
        self.assertGreaterEqual(len(self.models), 20)
        for instance, object_id in self.models:
            self.repository.save_artifact(
                instance, object_id=object_id, source_version=SOURCE_VERSION
            )
        for instance, object_id in self.models:
            reloaded = self.repository.load_artifact(
                type(instance), object_id=object_id, source_version=SOURCE_VERSION
            )
            self.assertIsNotNone(reloaded, object_id)
            assert reloaded is not None
            self.assertEqual(
                reloaded.model_dump(mode="json"),
                instance.model_dump(mode="json"),
                object_id,
            )

    def test_resaving_identical_content_is_idempotent(self) -> None:
        instance, object_id = self.models[0]
        first = self.repository.save_artifact(
            instance, object_id=object_id, source_version=SOURCE_VERSION
        )
        second = self.repository.save_artifact(
            instance, object_id=object_id, source_version=SOURCE_VERSION
        )
        self.assertEqual(first.content_hash, second.content_hash)

    def test_changed_content_under_the_same_version_is_refused(self) -> None:
        gap = KnowledgeGap.model_validate_json(
            (REFINEMENT / "knowledge_gap.json").read_text()
        )
        self.repository.save_artifact(
            gap, object_id=gap.gap_id, source_version=SOURCE_VERSION
        )
        with self.assertRaises(ValueError):
            self.repository.save_artifact(
                gap.model_copy(update={"status": "CLOSED"}),
                object_id=gap.gap_id,
                source_version=SOURCE_VERSION,
            )

    def test_lineage_chain_is_retrievable(self) -> None:
        lineage = json.loads((ACTION / "lineage.json").read_text())
        experiment_id = lineage["experiment_id"]
        self.repository.add_lineage(
            parent_id=lineage["knowledge_gap_id"],
            child_id=experiment_id,
            relationship="TESTS",
        )
        for item in lineage["required_capabilities"]:
            self.repository.add_lineage(
                parent_id=experiment_id,
                child_id=item["capability_id"],
                relationship="REQUIRES",
                evidence_ids=(item["evidence_source"],),
            )
        to_experiment = self.repository.lineage_to(experiment_id)
        self.assertTrue(to_experiment)
        self.assertIn("TESTS", {relation for _, relation, _ in to_experiment})


if __name__ == "__main__":
    unittest.main()
