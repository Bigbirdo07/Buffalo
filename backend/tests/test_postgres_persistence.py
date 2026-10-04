"""Postgres-dialect persistence tests.

Skipped unless a server is reachable, so the default suite needs no database.
Set ATLAS_TEST_DATABASE_URL to point at one, or rely on the local default.

These cover what SQLite cannot: real concurrency on the uniqueness constraint,
Postgres type handling for the JSON payload columns, and that the immutability
guarantee is enforced by the database rather than only by the Python pre-check.
"""

from __future__ import annotations

import json
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy import text

from atlas.domain.gaps import KnowledgeGap
from atlas.persistence.database import create_engine_for_url, create_schema
from atlas.persistence.repository import AtlasRepository

ROOT = Path(__file__).parents[2]
DEFAULT_URL = "postgresql+psycopg://atlas:atlas@localhost:5432/atlas"
URL = os.environ.get("ATLAS_TEST_DATABASE_URL", DEFAULT_URL)


def _server_available() -> bool:
    try:
        engine = create_engine_for_url(URL)
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        return True
    except Exception:
        return False


AVAILABLE = _server_available()


@unittest.skipUnless(AVAILABLE, f"no Postgres server reachable at {URL}")
class PostgresPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine_for_url(URL)
        create_schema(cls.engine)

    def setUp(self) -> None:
        self.repository = AtlasRepository(self.engine)
        self.version = f"test-{uuid.uuid4().hex[:12]}"
        self.gap = KnowledgeGap.model_validate_json(
            (ROOT / "data/refinement/scar16_stub1_e3/knowledge_gap.json").read_text()
        )

    def tearDown(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text("delete from artifacts where source_version = :version"),
                {"version": self.version},
            )

    def _save(self, model: KnowledgeGap) -> str:
        record = self.repository.save_artifact(
            model, object_id="pg-test:gap", source_version=self.version
        )
        return record.content_hash

    def test_dialect_is_postgresql(self) -> None:
        self.assertEqual(self.engine.dialect.name, "postgresql")

    def test_round_trip_is_lossless_on_postgres(self) -> None:
        self._save(self.gap)
        reloaded = self.repository.load_artifact(
            KnowledgeGap, object_id="pg-test:gap", source_version=self.version
        )
        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertEqual(reloaded.model_dump(mode="json"), self.gap.model_dump(mode="json"))

    def test_nested_payload_survives_the_json_column(self) -> None:
        self._save(self.gap)
        with self.engine.connect() as connection:
            stored = connection.execute(
                text(
                    "select payload from artifacts where object_id = 'pg-test:gap' "
                    "and source_version = :version"
                ),
                {"version": self.version},
            ).scalar_one()
        payload = stored if isinstance(stored, dict) else json.loads(stored)
        self.assertEqual(payload["gap_id"], self.gap.gap_id)
        # Deeply nested structure must survive, not just scalars.
        self.assertEqual(
            len(payload["search_coverage"]["sources"]),
            len(self.gap.search_coverage.sources),
        )

    def test_database_enforces_version_uniqueness(self) -> None:
        self._save(self.gap)
        with self.engine.connect() as connection:
            constraints = connection.execute(
                text(
                    "select pg_get_constraintdef(oid) from pg_constraint "
                    "where conrelid = 'artifacts'::regclass and contype = 'u'"
                )
            ).scalars().all()
        self.assertTrue(
            any("object_id" in item and "source_version" in item for item in constraints),
            "immutability must be guaranteed by a database constraint",
        )

    def test_changed_content_is_refused_as_a_domain_error(self) -> None:
        self._save(self.gap)
        with self.assertRaises(ValueError):
            self._save(self.gap.model_copy(update={"status": "CLOSED"}))

    def test_concurrent_identical_writes_are_idempotent(self) -> None:
        """Losing the insert race must reconcile, not surface a driver error."""
        with ThreadPoolExecutor(max_workers=8) as pool:
            hashes = list(pool.map(lambda _: self._save(self.gap), range(8)))
        self.assertEqual(len(set(hashes)), 1)
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "select count(*) from artifacts where object_id = 'pg-test:gap' "
                    "and source_version = :version"
                ),
                {"version": self.version},
            ).scalar_one()
        self.assertEqual(rows, 1)

    def test_concurrent_conflicting_writes_raise_the_domain_error(self) -> None:
        self._save(self.gap)

        def write(index: int) -> str:
            try:
                self._save(self.gap.model_copy(update={"status": f"VARIANT-{index}"}))
            except ValueError:
                return "ValueError"
            return "OK"

        with ThreadPoolExecutor(max_workers=6) as pool:
            outcomes = set(pool.map(write, range(6)))
        self.assertEqual(outcomes, {"ValueError"})

    def test_reviews_remain_append_only_on_postgres(self) -> None:
        from datetime import UTC, datetime

        from atlas.domain.reviews import (
            ReviewTargetType,
            ScientificReview,
            ScientificReviewStatus,
        )

        base = {
            "target_type": ReviewTargetType.KNOWLEDGE_GAP,
            "target_id": f"pg-test:{self.version}",
            "original_value": {"status": "OPEN"},
            "reviewer_name": "test reviewer",
            "reviewer_role": "test",
            "source_version": self.version,
            "software_version": "test",
        }
        first = ScientificReview(
            review_id=f"review:{self.version}:1",
            status=ScientificReviewStatus.PENDING,
            **base,
        )
        second = ScientificReview(
            review_id=f"review:{self.version}:2",
            status=ScientificReviewStatus.APPROVED,
            reviewed_at=datetime.now(UTC),
            scientific_rationale="approved in test",
            **base,
        )
        self.repository.append_review(first)
        self.repository.append_review(second)
        stored = self.repository.reviews_for(str(base["target_id"]))
        self.assertEqual(len(stored), 2)
        self.assertEqual(
            {item.status for item in stored},
            {ScientificReviewStatus.PENDING, ScientificReviewStatus.APPROVED},
        )
        with self.engine.begin() as connection:
            connection.execute(
                text("delete from scientific_reviews where source_version = :v"),
                {"v": self.version},
            )


if __name__ == "__main__":
    unittest.main()
