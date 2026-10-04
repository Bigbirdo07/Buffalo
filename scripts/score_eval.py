#!/usr/bin/env python3
"""Score a completed adjudication against the engine and log every disagreement.

Reports three things separately, because they have different fixes:

* **status agreement** -- the engine and the reviewer assigned the same category
  from the same evidence. A disagreement here is a rules problem, and the rule
  that fired is named so it can be argued with.
* **extraction disputes** -- the reviewer rejected how evidence was
  characterised. That is an extraction problem, and it is tracked separately
  because manual extraction is where this project's errors have been.
* **directional bias** -- whether the engine reads systematically stronger or
  weaker than the reviewer, which matters more than the raw rate. An engine that
  errs toward caution is a different instrument from one that overclaims.

Nothing here is a pass mark. A low agreement rate is a finding, not a failure,
and the disagreement log is the useful output either way.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# Ordered weakest to strongest claim about the evidence, for directional bias.
STRENGTH = {
    "INSUFFICIENT_EVIDENCE": 0,
    "CONTRADICTED": 0,
    "PARTIALLY_SUPPORTED": 1,
    "CONTEXT_DEPENDENT": 1,
    "SUPPORTED": 2,
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-dir", type=Path, default=ROOT / "data/eval/round-1")
    parser.add_argument("--responses", type=Path, default=None)
    args = parser.parse_args()
    eval_dir = args.eval_dir
    responses_path = args.responses or (eval_dir / "responses.json")
    if not responses_path.exists():
        raise SystemExit(
            f"no completed responses at {responses_path}. Fill in "
            f"{eval_dir / 'responses_template.json'} and save it as responses.json."
        )

    worksheet = _load(eval_dir / "worksheet.json")
    key = _load(eval_dir / "answer_key.json")
    responses = _load(responses_path)

    actual = sha256((eval_dir / "worksheet.json").read_bytes()).hexdigest()
    if actual != key["worksheet_sha256"]:
        raise SystemExit(
            "worksheet has changed since the answer key was written; regenerate both "
            "so the adjudication refers to the evidence actually shown"
        )

    items = {item["item_id"]: item for item in worksheet["items"]}
    answers = key["answers"]
    rows: list[dict[str, Any]] = []
    for response in responses["responses"]:
        item_id = response["item_id"]
        reviewer = (response.get("reviewer_status") or "").strip().upper()
        if not reviewer:
            continue
        if item_id not in answers:
            raise SystemExit(f"response refers to unknown item {item_id!r}")
        engine = answers[item_id]["engine_status"]
        rows.append(
            {
                "item_id": item_id,
                "disease": items[item_id]["disease"],
                "atomic_claim": items[item_id]["atomic_claim"],
                "engine_status": engine,
                "reviewer_status": reviewer,
                "agree": engine == reviewer,
                "rule_applied": answers[item_id]["rule_applied"],
                "extraction_disputed": bool(response.get("extraction_disputed")),
                "note": response.get("note", ""),
                "engine_strength": STRENGTH.get(engine),
                "reviewer_strength": STRENGTH.get(reviewer),
            }
        )

    if not rows:
        raise SystemExit("no adjudicated items found; every reviewer_status was blank")

    adjudicated = len(rows)
    agreed = sum(1 for row in rows if row["agree"])
    disputes = [row for row in rows if row["extraction_disputed"]]
    disagreements = [row for row in rows if not row["agree"]]
    stronger = sum(
        1
        for row in rows
        if row["engine_strength"] is not None
        and row["reviewer_strength"] is not None
        and row["engine_strength"] > row["reviewer_strength"]
    )
    weaker = sum(
        1
        for row in rows
        if row["engine_strength"] is not None
        and row["reviewer_strength"] is not None
        and row["engine_strength"] < row["reviewer_strength"]
    )
    by_rule = Counter(row["rule_applied"] for row in disagreements)
    bias = (
        "Engine reads more cautiously than the reviewer"
        if weaker > stronger
        else "Engine reads more strongly than the reviewer"
        if stronger > weaker
        else "No directional bias in this round"
    )

    report: dict[str, Any] = {
        "schema_version": "eval-agreement-v1",
        "reviewer": {
            "name": responses.get("reviewer_name") or "unnamed",
            "role": responses.get("reviewer_role") or "unstated",
            "reviewed_on": responses.get("reviewed_on") or "unstated",
        },
        "worksheet_sha256": actual,
        "items_total": len(items),
        "items_adjudicated": adjudicated,
        "status_agreement": {
            "agreed": agreed,
            "disagreed": len(disagreements),
            "rate": round(agreed / adjudicated, 3),
        },
        "directional_bias": {
            "engine_stronger_than_reviewer": stronger,
            "engine_weaker_than_reviewer": weaker,
            "interpretation": bias,
        },
        "extraction_disputes": {
            "count": len(disputes),
            "items": [row["item_id"] for row in disputes],
            "note": (
                "An extraction dispute is an error in how evidence was characterised, "
                "not in the rules. Manual extraction is the least validated step."
            ),
        },
        "disagreements_by_rule": dict(by_rule.most_common()),
        "disagreements": [
            {
                "item_id": row["item_id"],
                "disease": row["disease"],
                "atomic_claim": row["atomic_claim"],
                "engine_status": row["engine_status"],
                "engine_rule": row["rule_applied"],
                "reviewer_status": row["reviewer_status"],
                "extraction_disputed": row["extraction_disputed"],
                "reviewer_note": row["note"],
            }
            for row in disagreements
        ],
        "per_item": rows,
        "caveats": [
            (f"n = {adjudicated}. A rate computed over single digits is indicative, "
            "not an estimate with a usable confidence interval."),
            "One reviewer, so no inter-rater reliability is measurable.",
            ("The reviewer saw the extractor's effect labels and system descriptions, "
            "so extraction errors can propagate into an apparent agreement."),
        ],
    }
    # Name the report after the responses it scored, so a trial run can never
    # overwrite a real adjudication.
    stem = responses_path.stem
    suffix = "" if stem == "responses" else stem.removeprefix("responses")
    report_path = eval_dir / f"agreement_report{suffix}.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "report": str(report_path),
                "adjudicated": adjudicated,
                "agreement_rate": round(agreed / adjudicated, 3),
                "disagreements": len(disagreements),
                "extraction_disputes": len(disputes),
                "directional_bias": bias,
                "disagreements_by_rule": dict(by_rule.most_common()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
