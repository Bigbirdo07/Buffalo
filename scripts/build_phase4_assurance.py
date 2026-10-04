#!/usr/bin/env python3
"""Build and verify the Phase 4 action-bundle reproducibility manifest.

Fails closed: the bundle is rebuilt from the cache into a temporary directory and
compared byte-for-byte against the committed artifacts. The Phase 4 bundle is
fully deterministic (its as-of instant comes from the snapshot cache, not the
clock), so no canonicalization is permitted here.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any

BUNDLE_FILES = (
    "required_capabilities.json",
    "required_assets.json",
    "discovery_queries.json",
    "researchers.json",
    "entity_resolution.json",
    "laboratories.json",
    "capability_claims.json",
    "research_assets.json",
    "organizations.json",
    "grants.json",
    "clinical_studies.json",
    "search_coverage.json",
    "collaboration_opportunity.json",
    "patient_explanation.json",
    "scientist_explanation.json",
    "lineage.json",
)

IMPLEMENTATION_FILES = (
    "backend/src/atlas/domain/action.py",
    "backend/src/atlas/domain/discovery.py",
    "backend/src/atlas/domain/reviews.py",
    "backend/src/atlas/services/action_discovery.py",
    "backend/src/atlas/services/requirement_extraction.py",
    "backend/src/atlas/adapters/literature/client.py",
    "backend/src/atlas/adapters/nih_reporter/client.py",
    "backend/src/atlas/adapters/clinical_trials/client.py",
    "backend/src/atlas/adapters/web_assets/brightdata.py",
    "scripts/build_phase4_action.py",
    "scripts/build_phase4_assurance.py",
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _verify_snapshots(snapshot_dir: Path, root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for metadata_path in sorted(snapshot_dir.glob("*.json")):
        metadata = json.loads(metadata_path.read_text())
        body = metadata_path.with_suffix(".body")
        if not body.exists():
            raise SystemExit(f"cached snapshot body missing: {body}")
        actual = _sha256(body)
        if actual != metadata["sha256"]:
            raise SystemExit(
                f"cached snapshot hash mismatch for {body}: "
                f"recorded {metadata['sha256']}, actual {actual}"
            )
        records.append(
            {
                "metadata": str(metadata_path.relative_to(root)),
                "body": str(body.relative_to(root)),
                "sha256": actual,
                "url": metadata.get("url"),
                "matches": True,
            }
        )
    return records


def verify_rebuild(root: Path, input_dir: Path, output_dir: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "backend" / "src")
    with tempfile.TemporaryDirectory(prefix="phase4-assurance-") as name:
        temp = Path(name) / "bundle"
        # The rebuild reads the committed snapshot cache; copy it so the temporary
        # bundle resolves the same bytes without writing into the committed tree.
        temp.mkdir(parents=True)
        subprocess.run(
            [
                "cp",
                "-R",
                str(output_dir / "snapshots"),
                str(temp / "snapshots"),
            ],
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "scripts/build_phase4_action.py",
                "--input",
                str(input_dir),
                "--output",
                str(temp),
                "--offline",
            ],
            cwd=root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        results: dict[str, Any] = {}
        mismatched = []
        for name_ in BUNDLE_FILES:
            committed = output_dir / name_
            rebuilt = temp / name_
            if not rebuilt.exists():
                raise SystemExit(f"rebuild did not produce {name_}")
            committed_hash = _sha256(committed)
            rebuilt_hash = _sha256(rebuilt)
            identical = committed_hash == rebuilt_hash
            results[name_] = {
                "committed_sha256": committed_hash,
                "rebuilt_sha256": rebuilt_hash,
                "byte_identical": identical,
            }
            if not identical:
                mismatched.append(name_)
        if mismatched:
            raise SystemExit(
                "offline rebuild is not byte-identical for: " + ", ".join(mismatched)
            )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/refinement/scar16_stub1_e3"))
    parser.add_argument("--output", type=Path, default=Path("data/action/scar16_stub1_e3"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    input_dir = (root / args.input).resolve()
    output_dir = (root / args.output).resolve()

    phase3 = {
        name: _sha256(input_dir / name)
        for name in (
            "knowledge_gap.json",
            "experiment_proposal.json",
            "edge_refinement.json",
            "claim_lineage.json",
            "reproducibility_manifest.json",
        )
    }
    dependencies = {}
    for package in ("pydantic", "PyYAML", "SQLAlchemy", "ruff", "mypy", "pytest"):
        try:
            dependencies[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            dependencies[package] = "NOT_INSTALLED"

    lineage = json.loads((output_dir / "lineage.json").read_text())
    coverage = json.loads((output_dir / "search_coverage.json").read_text())
    collaboration = json.loads((output_dir / "collaboration_opportunity.json").read_text())
    rebuild = verify_rebuild(root, input_dir, output_dir)

    manifest = {
        "schema_version": "phase4-reproducibility-v1",
        "as_of": lineage["as_of"],
        "as_of_basis": lineage["as_of_basis"],
        "workspace_revision": {
            "git_commit": None,
            "status": "NOT_A_GIT_WORKTREE",
            "compensating_control": "Per-file implementation hashes are recorded below.",
        },
        "environment": {
            "python": sys.version.split()[0],
            "dependencies": dependencies,
        },
        "phase3_inputs_sha256": phase3,
        "implementation_sha256": {
            name: _sha256(root / name) for name in sorted(IMPLEMENTATION_FILES)
        },
        "artifact_sha256": {
            name: _sha256(output_dir / name) for name in sorted(BUNDLE_FILES)
        },
        "cached_snapshots": {
            "action": _verify_snapshots(output_dir / "snapshots", root),
            "refinement_reused": len(list((input_dir / "snapshots").glob("*.body"))),
        },
        "offline_rebuild": {
            "status": "PASS",
            "network_required": False,
            "canonicalization": "none; the bundle is byte-identical across runs",
            "results": rebuild,
        },
        "source_coverage_summary": [
            {
                "source": item["source"],
                "status": item["status"],
                "result_count": item["result_count"],
                "error": item["error"],
            }
            for item in coverage["sources"]
        ],
        "collaboration_status": collaboration["status"],
        "missing_capability_count": len(collaboration["missing_capabilities"]),
        "commands": [
            "PYTHONPATH=backend/src .venv/bin/python scripts/build_phase4_action.py --offline",
            "PYTHONPATH=backend/src .venv/bin/python scripts/build_phase4_assurance.py",
            "make check",
        ],
        "human_review": {
            "status": "PENDING",
            "required": True,
            "note": (
                "Requirement extraction and rule-based capability verification are "
                "deterministic software outputs, not expert scientific review. No "
                "collaborator was contacted and no capability was confirmed with any person "
                "or institution."
            ),
        },
    }
    target = output_dir / "reproducibility_manifest.json"
    target.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "manifest": str(target),
                "offline_rebuild": manifest["offline_rebuild"]["status"],
                "artifacts": len(BUNDLE_FILES),
                "action_snapshots": len(manifest["cached_snapshots"]["action"]),
                "collaboration_status": manifest["collaboration_status"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
