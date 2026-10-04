#!/usr/bin/env python3
"""Build and verify the Phase 3 lineage and reproducibility records.

This is an assurance script, not a new application layer. It derives both files
from the already validated Phase 3 artifacts and fails closed if cached replay
does not reproduce their scientific content.
"""

from __future__ import annotations

import argparse
import ast
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any

VOLATILE_KEYS = frozenset(
    {
        "created_at",
        "last_reviewed_at",
        "checked_at",
        "search_started_at",
        "search_completed_at",
    }
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def verify_snapshot_body(meta_path: Path) -> tuple[Path, str]:
    """Return the body and digest, or fail closed when cached bytes changed."""
    meta = _load(meta_path)
    body_path = meta_path.with_suffix(".body")
    if not body_path.exists():
        raise ValueError(f"cached snapshot body is missing: {body_path}")
    actual = _sha256(body_path)
    if actual != meta["sha256"]:
        raise ValueError(
            f"cached snapshot hash mismatch for {body_path}: "
            f"recorded {meta['sha256']}, actual {actual}"
        )
    return body_path, actual


def canonicalize(value: Any) -> Any:
    """Remove only volatile execution timestamps; preserve scientific content."""
    if isinstance(value, dict):
        return {
            key: canonicalize(item)
            for key, item in sorted(value.items())
            if key not in VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    return value


def _canonical_sha(value: Any) -> str:
    encoded = json.dumps(
        canonicalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return sha256(encoded).hexdigest()


def reachable_atlas_modules(root: Path, entry_points: list[Path]) -> set[Path]:
    """Return the atlas modules the Phase 3 entry points actually import.

    The manifest must pin the code that produced the scientific result and nothing
    else. Hashing every module in the package made the Phase 3 record depend on
    unrelated later development, which both broke the record for non-scientific
    reasons and diluted what it certified. The set is computed from the import
    graph so it stays correct without manual maintenance.
    """
    source_root = root / "backend" / "src"
    pending = [path for path in entry_points]
    seen_files: set[Path] = set()
    modules: set[Path] = set()
    while pending:
        current = pending.pop()
        if current in seen_files or not current.exists():
            continue
        seen_files.add(current)
        tree = ast.parse(current.read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names.add(node.module)
                names.update(f"{node.module}.{alias.name}" for alias in node.names)
        for name in names:
            if not name.startswith("atlas"):
                continue
            parts = name.split(".")
            candidates = (
                source_root.joinpath(*parts).with_suffix(".py"),
                source_root.joinpath(*parts, "__init__.py"),
            )
            for candidate in candidates:
                if candidate.exists():
                    modules.add(candidate)
                    pending.append(candidate)
            package_init = source_root.joinpath(*parts[:-1], "__init__.py")
            if package_init.exists():
                modules.add(package_init)
                pending.append(package_init)
    return modules


def build_lineage(run_dir: Path) -> dict[str, object]:
    refinement = _load(run_dir / "edge_refinement.json")
    gap = _load(run_dir / "knowledge_gap.json")
    experiment = _load(run_dir / "experiment_proposal.json")
    checks_by_evidence: dict[str, set[str]] = {}
    for check in refinement["citation_checks"]:
        checks_by_evidence.setdefault(check["evidence_id"], set()).update(
            check["source_snapshot_sha256"]
        )

    observations = []
    for item in refinement["observations"]:
        observations.append(
            {
                "observation_id": item["observation_id"],
                "evidence_id": item["evidence_id"],
                "source_identifier": item["source_identifier"],
                "origin": item["origin"],
                "claim_ids": item["claim_ids"],
                "readout": item["readout"],
                "effect": item["effect"],
                "source_snapshot_sha256": sorted(
                    checks_by_evidence.get(item["evidence_id"], set())
                ),
            }
        )

    atomic = []
    for item in refinement["atomic"]:
        atomic.append(
            {
                "claim_id": item["claim"]["claim_id"],
                "derived_from_claim_ids": item["claim"]["derived_from_claim_ids"],
                "statement": item["claim"]["normalized_statement"],
                "status": item["status"],
                "rule_applied": item["rule_applied"],
                "evidence_by_role": {
                    "direct_supporting": item["direct_supporting"],
                    "direct_refuting": item["direct_refuting"],
                    "direct_qualifying": item["direct_qualifying"],
                    "indirect": item["indirect"],
                    "background_only": item["background_only"],
                },
            }
        )

    upstream = refinement["upstream_claim"]
    return {
        "schema_version": "phase3-claim-lineage-v1",
        "run_id": refinement["run_id"],
        "lineage": [
            "DisMech curated claim",
            "atomic extracted claims",
            "source observations",
            "independent deterministic reviews",
            "categorical synthesis",
            "KnowledgeGap",
            "ExperimentProposal",
        ],
        "upstream": {
            "kind": "CURATED",
            "claim_id": upstream["claim_id"],
            "edge_id": refinement["upstream_edge_id"],
            "statement": upstream["normalized_statement"],
            "source_version": upstream["provenance"]["source_version"],
            "source_locator": upstream["provenance"]["source_object_path"],
            "source_snapshot_sha256": upstream["provenance"]["source_snapshot_sha256"],
            "evidence_ids": refinement["upstream_evidence_ids"],
        },
        "atomic_claims": atomic,
        "observations": observations,
        "reviews": [
            {
                "claim_id": item["claim_id"],
                "observation_id": item["source_id"],
                "fit": item["supports"],
                "directness": item["directness"],
                "causal_support": item["causal_support"],
            }
            for item in refinement["reviews"]
        ],
        "synthesis": {
            "edge_status": refinement["edge_status"],
            "edge_rule_applied": refinement["edge_rule_applied"],
            "recommended_scope": refinement["recommended_scope"],
        },
        "knowledge_gap": {
            "gap_id": gap["gap_id"],
            "related_claims": gap["related_claims"],
            "related_edges": gap["related_edges"],
            "status": gap["status"],
        },
        "experiment_proposal": {
            "experiment_id": experiment["experiment_id"],
            "knowledge_gap_id": experiment["knowledge_gap_id"],
            "label": experiment["label"],
            "human_review_required": experiment["human_review_required"],
        },
        "human_review": {
            "status": "PENDING",
            "required": True,
            "note": "Deterministic criticism and synthesis are not expert scientific review.",
        },
    }


def verify_offline(root: Path, run_dir: Path) -> dict[str, dict[str, object]]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "backend" / "src")
    commands = [
        (
            "refinement",
            [
                sys.executable,
                "scripts/refine_edge.py",
                str(run_dir.relative_to(root)),
                "--offline",
                "--output",
            ],
            run_dir / "edge_refinement.json",
        )
    ]
    results: dict[str, dict[str, object]] = {}
    with tempfile.TemporaryDirectory(prefix="phase3-assurance-") as temp_name:
        temp = Path(temp_name)
        regenerated_edge = temp / "edge_refinement.json"
        command = [*commands[0][1], str(regenerated_edge)]
        subprocess.run(command, cwd=root, env=env, check=True, capture_output=True, text=True)
        subprocess.run(
            [
                sys.executable,
                "scripts/build_gap_and_experiment.py",
                str(regenerated_edge),
                "--gap-output",
                str(temp / "knowledge_gap.json"),
                "--experiment-output",
                str(temp / "experiment_proposal.json"),
            ],
            cwd=root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        for name in ("edge_refinement", "knowledge_gap", "experiment_proposal"):
            committed = _load(run_dir / f"{name}.json")
            regenerated = _load(temp / f"{name}.json")
            committed_sha = _canonical_sha(committed)
            regenerated_sha = _canonical_sha(regenerated)
            results[name] = {
                "matches": committed_sha == regenerated_sha,
                "committed_canonical_sha256": committed_sha,
                "regenerated_canonical_sha256": regenerated_sha,
            }
    if not all(bool(item["matches"]) for item in results.values()):
        raise SystemExit("offline reproduction differs from committed artifacts")
    return results


def build_manifest(
    root: Path,
    run_dir: Path,
    lineage_path: Path,
    reproduction: dict[str, dict[str, object]],
) -> dict[str, object]:
    plan = _load(run_dir / "observation_plan.json")
    source_path = root / plan["target"]["disease_file"]
    snapshot_records = []
    for meta_path in sorted((run_dir / "snapshots").glob("*.json")):
        meta = _load(meta_path)
        body_path, actual = verify_snapshot_body(meta_path)
        snapshot_records.append(
            {
                "metadata": str(meta_path.relative_to(root)),
                "body": str(body_path.relative_to(root)),
                "recorded_sha256": meta["sha256"],
                "actual_sha256": actual,
                "matches": actual == meta["sha256"],
            }
        )
    entry_points = [
        root / "scripts" / "refine_edge.py",
        root / "scripts" / "build_gap_and_experiment.py",
        root / "scripts" / "build_phase3_assurance.py",
        root / "scripts" / "audit_corpus.py",
        root / "scripts" / "build_fixtures.py",
    ]
    implementation_paths = sorted(
        {
            *entry_points,
            *reachable_atlas_modules(root, entry_points),
            root / "backend" / "pyproject.toml",
        }
    )
    artifact_paths = [
        run_dir / "observation_plan.json",
        run_dir / "observations.json",
        run_dir / "edge_refinement.json",
        run_dir / "knowledge_gap.json",
        run_dir / "experiment_proposal.json",
        lineage_path,
        root / "data" / "audit" / "corpus_audit.json",
        root / "data" / "audit" / "candidate_metrics.json",
        root / "data" / "audit" / "pubmed_activity.json",
        root / "data" / "fixtures" / "real" / "MANIFEST.json",
        root / "docs" / "REAL_IMPORT_AUDIT.md",
        root / "docs" / "DEMO_DISEASE_CANDIDATES.md",
        root / "docs" / "SCIENTIFIC_DECISIONS.md",
        root / "docs" / "PHASE_3_ACCEPTANCE.md",
    ]
    dependencies = {}
    for package in ("pydantic", "PyYAML", "ruff", "mypy"):
        try:
            dependencies[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            dependencies[package] = "NOT_INSTALLED"
    return {
        "schema_version": "phase3-reproducibility-v1",
        "source": {
            "name": "DisMech",
            "commit": plan["target"]["dismech_commit"],
            "file": plan["target"]["disease_file"],
            "sha256": _sha256(source_path),
        },
        "workspace_revision": {
            "git_commit": None,
            "status": "NOT_A_GIT_WORKTREE",
            "compensating_control": "Per-file implementation hashes are recorded below.",
        },
        "environment": {
            "python": sys.version.split()[0],
            "dependencies": dependencies,
        },
        "implementation_scope": (
            "Phase 3 entry-point scripts, the atlas modules reachable from their import "
            "graph, and the package build file. Modules not imported by the Phase 3 "
            "pipeline are deliberately excluded so later development cannot invalidate "
            "this scientific record."
        ),
        "implementation_sha256": {
            str(path.relative_to(root)): _sha256(path) for path in implementation_paths
        },
        "artifact_sha256": {
            str(path.relative_to(root)): _sha256(path) for path in artifact_paths
        },
        "cached_snapshots": {
            "count": len(snapshot_records),
            "all_hashes_match": True,
            "records": snapshot_records,
        },
        "offline_reproduction": {
            "status": "PASS",
            "network_required": False,
            "canonicalization": {
                "excluded_keys": sorted(VOLATILE_KEYS),
                "reason": "Execution timestamps vary while scientific content is invariant.",
            },
            "results": reproduction,
        },
        "commands": [
            (
                "PYTHONPATH=backend/src .venv/bin/python scripts/refine_edge.py "
                "data/refinement/scar16_stub1_e3 --offline --output <temporary-output>"
            ),
            (
                ".venv/bin/python scripts/build_gap_and_experiment.py <temporary-output> "
                "--gap-output <temporary-gap> --experiment-output <temporary-experiment>"
            ),
            "make check",
        ],
        "human_review": {
            "status": "PENDING",
            "required": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-dir", type=Path, default=Path("data/refinement/scar16_stub1_e3")
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    run_dir = (root / args.run_dir).resolve()
    lineage_path = run_dir / "claim_lineage.json"
    manifest_path = run_dir / "reproducibility_manifest.json"
    _write(lineage_path, build_lineage(run_dir))
    reproduction = verify_offline(root, run_dir)
    _write(manifest_path, build_manifest(root, run_dir, lineage_path, reproduction))
    print(json.dumps({"lineage": str(lineage_path), "manifest": str(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
