#!/usr/bin/env python3
"""Build a blinded adjudication worksheet from completed refinement runs.

The point is to measure the engine instead of asserting it is right. The
worksheet contains everything a reviewer needs to judge each atomic claim --
scope, every piece of evidence, each span, and each citation's verification
status -- and deliberately omits the engine's own status, the rule that fired,
and the critic's per-evidence verdicts. The answer key is written to a separate
file so the blinding is real rather than nominal.

Two distinct error sources are collected separately, because they have different
fixes:

* **status disagreement** -- the reviewer would assign a different category from
  the same evidence. That is a rules problem.
* **extraction dispute** -- the reviewer rejects how the evidence was
  characterised (an effect label, a system description, a claim's scope). That is
  an extraction problem, and the manual extraction step is where this project's
  errors have actually been.

Claim order is deterministically shuffled with a fixed seed so grouping by
disease or by status cannot hint at an answer.
"""

from __future__ import annotations

import argparse
import json
import random
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS = {
    "SCAR16": ROOT / "data/refinement/scar16_stub1_e3",
    "SCAR20": ROOT / "data/refinement/scar20_snx14_autophagy",
}
STATUS_OPTIONS = (
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "CONTEXT_DEPENDENT",
    "INSUFFICIENT_EVIDENCE",
    "CONTRADICTED",
    "UNREVIEWED",
)
SHUFFLE_SEED = 20261003


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def collect(run_dirs: dict[str, Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return blinded items and the separate answer key."""
    items: list[dict[str, Any]] = []
    key: dict[str, Any] = {}
    for disease, run_dir in run_dirs.items():
        refinement = _load(run_dir / "edge_refinement.json")
        plan = _load(run_dir / "observation_plan.json")
        specs = {spec["claim_id"]: spec for spec in plan["atomic_claims"]}
        observations = {item["observation_id"]: item for item in refinement["observations"]}
        checks = {item["evidence_id"]: item for item in refinement["citation_checks"]}
        for atomic in refinement["atomic"]:
            claim = atomic["claim"]
            # Recover the plan id, since the stored claim id is the plan's own key.
            spec = specs.get(claim["claim_id"], {})
            evidence_rows = []
            for review in refinement["reviews"]:
                if review["claim_id"] != claim["claim_id"]:
                    continue
                observation = observations[review["source_id"]]
                check = checks.get(observation["evidence_id"], {})
                evidence_rows.append(
                    {
                        "observation_id": observation["observation_id"],
                        "source": observation["source_identifier"],
                        "upstream_reference_form": observation.get(
                            "upstream_reference_form"
                        ),
                        "origin": observation["origin"],
                        "effect_as_extracted": observation["effect"],
                        "readout": observation["readout"],
                        "species": observation["species"],
                        "cell_types": observation.get("cell_types") or [],
                        "variants": observation["variants"],
                        "variant_class": observation.get("variant_class"),
                        "disease_entity": observation["disease_entity"],
                        "experimental_system": observation["experimental_system"],
                        "span": observation["support_span"],
                        "span_location": observation["source_location"],
                        "citation_status": check.get("status", "NOT_CHECKED"),
                        "full_text_available": check.get("full_text_available"),
                        "extraction_note": observation.get("extraction_note"),
                    }
                )
            items.append(
                {
                    "item_id": f"{disease}:{claim['claim_id']}",
                    "disease": disease,
                    "gene": plan["target"]["gene"],
                    "upstream_edge_claim": refinement["upstream_claim"][
                        "normalized_statement"
                    ],
                    "atomic_claim": claim["normalized_statement"],
                    "scope": {
                        "variants": spec.get("variant_scope", []),
                        "allele_class": spec.get("scope_class"),
                        "cell_type_scope": spec.get("cell_type_scope", []),
                        "disease_scope": plan["target"]["disease_scope"],
                        "readout_family": plan["readout_family"],
                        "readouts_bearing_on_this_claim": (
                            spec.get("readout_scope") or plan["readout_family"]
                        ),
                        "expected_effect_if_true": ["abolished", "decreased"],
                    },
                    "evidence": evidence_rows,
                }
            )
            key[f"{disease}:{claim['claim_id']}"] = {
                "engine_status": atomic["status"],
                "rule_applied": atomic["rule_applied"],
                "engine_rationale": atomic["rationale"],
            }
    random.Random(SHUFFLE_SEED).shuffle(items)
    return items, key


def render_markdown(items: list[dict[str, Any]]) -> str:
    lines = [
        "# Blind adjudication worksheet",
        "",
        "Assign a status to each atomic claim **from the evidence shown**. The",
        "engine's own status, the rule it applied and its per-evidence verdicts are",
        "deliberately withheld; they are in a separate answer key.",
        "",
        "Record answers in `responses.json` (a template is generated alongside this",
        "file). For each item:",
        "",
        "- `reviewer_status`: one of " + ", ".join(f"`{s}`" for s in STATUS_OPTIONS),
        "- `extraction_disputed`: `true` if you reject how the evidence was",
        "  characterised (an effect label, a system description, the claim's scope)",
        "  rather than disagreeing about the status it implies",
        "- `note`: free text; most useful on any disagreement",
        "",
        "Status definitions as the engine uses them:",
        "",
        "| Status | Meaning |",
        "| --- | --- |",
        "| SUPPORTED | Direct evidence supports the claim, none refutes or qualifies it |",
        "| PARTIALLY_SUPPORTED | Only qualified or partial direct support |",
        "| CONTEXT_DEPENDENT | Direct evidence both supports and limits it: true in some contexts |",
        "| INSUFFICIENT_EVIDENCE | Not enough direct evidence to judge |",
        "| CONTRADICTED | Direct evidence refutes it, from independent publications |",
        "",
        "Citation statuses you will see:",
        "",
        "- `VERIFIED` — quoted span located in retrieved source text",
        "- `UPSTREAM_ATTESTED` — identifier resolves, curator recorded the quote, but",
        "  the text was not retrievable, so the quote is unconfirmed either way",
        "- `SPAN_NOT_LOCATED` — text *was* retrieved and the quote is not in it",
        "",
        f"{len(items)} items, order deterministically shuffled.",
        "",
        "---",
        "",
    ]
    for index, item in enumerate(items, start=1):
        lines += [
            f"## Item {index} — `{item['item_id']}`",
            "",
            f"**Disease / gene:** {item['disease']} / {item['gene']}",
            "",
            f"**Upstream edge claim:** {item['upstream_edge_claim']}",
            "",
            f"**Atomic claim to judge:** **{item['atomic_claim']}**",
            "",
            "**Scope**",
            "",
            f"- alleles: {', '.join(item['scope']['variants']) or 'not scoped'}",
            f"- allele class: {item['scope']['allele_class'] or 'n/a'}",
            f"- cell type scope: {', '.join(item['scope']['cell_type_scope']) or 'not scoped'}",
            f"- disease scope: {', '.join(item['scope']['disease_scope'])}",
            "- readouts bearing on this claim: "
            + ", ".join(item["scope"]["readouts_bearing_on_this_claim"]),
            "- readouts counted as this capability at all: "
            + ", ".join(item["scope"]["readout_family"]),
            "",
            f"**Evidence ({len(item['evidence'])} item(s))**",
            "",
        ]
        if not item["evidence"]:
            lines += ["_No evidence was linked to this claim._", ""]
        for row in item["evidence"]:
            lines += [
                f"- **{row['observation_id']}** · {row['source']}"
                + (
                    f" (upstream wrote `{row['upstream_reference_form']}`)"
                    if row["upstream_reference_form"]
                    and row["upstream_reference_form"] != row["source"]
                    else ""
                ),
                f"    - citation: **{row['citation_status']}**"
                + (
                    ", full text retrieved"
                    if row["full_text_available"]
                    else ", full text not retrieved"
                ),
                f"    - origin: {row['origin']}",
                (f"    - readout: {row['readout']} · effect as extracted: "
                f"**{row['effect_as_extracted']}**"),
                f"    - system: {row['experimental_system']}",
                (f"    - species: {row['species']} · cell types: "
                f"{', '.join(row['cell_types']) or 'not stated'}"),
                (f"    - alleles: {', '.join(row['variants']) or row['variant_class'] or 'not stated'}"
                f" · disease entity: {row['disease_entity']}"),
                f"    - span ({row['span_location']}): “{row['span'].strip()}”",
            ]
            if row["extraction_note"]:
                lines.append(f"    - extractor note: {row['extraction_note']}")
            lines.append("")
        lines += ["---", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/eval/round-1")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    items, key = collect(RUNS)
    worksheet = {
        "schema_version": "eval-worksheet-v1",
        "blinding": (
            "Engine statuses, applied rules and per-evidence critic verdicts are "
            "excluded from this file and held in answer_key.json."
        ),
        "shuffle_seed": SHUFFLE_SEED,
        "status_options": list(STATUS_OPTIONS),
        "items": items,
    }
    worksheet_path = args.output_dir / "worksheet.json"
    worksheet_path.write_text(
        json.dumps(worksheet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (args.output_dir / "worksheet.md").write_text(
        render_markdown(items), encoding="utf-8"
    )

    template = {
        "schema_version": "eval-responses-v1",
        "reviewer_name": "",
        "reviewer_role": "",
        "reviewed_on": "",
        "responses": [
            {
                "item_id": item["item_id"],
                "reviewer_status": "",
                "extraction_disputed": False,
                "note": "",
            }
            for item in items
        ],
    }
    responses_path = args.output_dir / "responses_template.json"
    responses_path.write_text(
        json.dumps(template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    key_payload = {
        "schema_version": "eval-answer-key-v1",
        "warning": "Do not read before adjudicating; this is the engine's output.",
        "worksheet_sha256": sha256(worksheet_path.read_bytes()).hexdigest(),
        "answers": key,
    }
    (args.output_dir / "answer_key.json").write_text(
        json.dumps(key_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # Blinding check: no engine status may appear in the item payload. The
    # allowed-answer list is checked separately, since naming the options is not
    # leaking an answer.
    item_text = json.dumps(items, ensure_ascii=False)
    leaked = [
        status
        for status in STATUS_OPTIONS
        if status != "UNREVIEWED" and status in item_text
    ]
    if leaked:
        raise SystemExit(f"worksheet items leak engine statuses: {leaked}")
    for forbidden in ("rule_applied", "engine_status", "engine_rationale"):
        if forbidden in item_text:
            raise SystemExit(f"worksheet items leak {forbidden!r}")
    markdown_text = (args.output_dir / "worksheet.md").read_text()
    # The markdown defines the statuses for the reviewer, so only the
    # machine-readable items are held to the no-status rule; assert the rule and
    # rationale never appear in either form.
    for forbidden in ("rule_applied", "engine_rationale", "rule A", "rule E"):
        if forbidden in markdown_text:
            raise SystemExit(f"worksheet markdown leaks {forbidden!r}")

    print(
        json.dumps(
            {
                "items": len(items),
                "by_disease": {
                    disease: sum(1 for item in items if item["disease"] == disease)
                    for disease in RUNS
                },
                "evidence_rows": sum(len(item["evidence"]) for item in items),
                "worksheet": str(worksheet_path),
                "worksheet_markdown": str(args.output_dir / "worksheet.md"),
                "responses_template": str(responses_path),
                "answer_key": str(args.output_dir / "answer_key.json"),
                "blinding_verified": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
