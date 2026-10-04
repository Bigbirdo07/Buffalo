# Evaluation: measuring the engine instead of asserting it

Every quality claim in this project has so far been the authors' own. This is the
harness that replaces assertion with a number, and — more usefully — with a log
of every disagreement and the rule that caused it.

```bash
PYTHONPATH=backend/src .venv/bin/python scripts/build_eval_worksheet.py
# adjudicate: fill in responses_template.json, save as responses.json
PYTHONPATH=backend/src .venv/bin/python scripts/score_eval.py
```

Round 1 is generated and **awaiting adjudication**:
[`data/eval/round-1/`](../data/eval/round-1/)

| File | Purpose |
| --- | --- |
| `worksheet.md` | Human-readable, blinded. What a reviewer reads. |
| `worksheet.json` | Same content, machine-readable. |
| `responses_template.json` | Blank form covering every item. |
| `answer_key.json` | The engine's statuses. Separate file; do not read before adjudicating. |
| `agreement_report.json` | Written by the scorer. |

Round 1 contains **9 atomic claims** across two diseases (5 SCAR16, 4 SCAR20) and
**26 evidence rows**.

## What makes the blinding real

The worksheet shows the claim, its scope, and every piece of evidence with its
span, origin, extracted effect, experimental system, species, cell type, allele
and citation-verification status. It withholds the engine's status, the rule that
fired, and the critic's per-evidence verdicts.

That withholding is enforced, not promised. The generator refuses to write a
worksheet whose item payload contains any status token, `rule_applied`,
`engine_status` or `engine_rationale`, and tests assert the same plus the absence
of `directness`, `causal_support`, `DIRECT` and `QUALIFIES` — because a reviewer
shown the critic's verdict would be reviewing the critic rather than the
evidence. The answer key stores the SHA-256 of the exact worksheet it answers,
and the scorer aborts if the worksheet has since changed.

Item order is shuffled with a fixed seed so that grouping by disease, or by
status, cannot hint at an answer.

## Two error sources, measured separately

They have different fixes, so collapsing them would be a mistake.

**Status disagreement** — the reviewer assigns a different category from the same
evidence. That is a *rules* problem, and the report names the rule that fired
(A1–A7, E1–E5) so the rule itself can be argued with rather than the verdict.

**Extraction dispute** — the reviewer rejects how evidence was characterised: an
effect label, a system description, a claim's scope. That is an *extraction*
problem. It is tracked separately because extraction is this project's least
validated step: it is hand-authored, and both SCAR20 authoring errors (a plan
declaring an identifier the upstream data lacks; a variant string conflating
allele with cell type) originated there.

## Directional bias matters more than the rate

With single-digit n, the agreement rate is indicative at best. The more
informative signal is *direction*: does the engine read systematically stronger
or weaker than the reviewer?

An engine that errs toward caution is a different instrument from one that
overclaims, and for evidence appraisal the first is the tolerable failure. The
report classifies each disagreement by claim strength
(`INSUFFICIENT_EVIDENCE`/`CONTRADICTED` < `PARTIALLY_SUPPORTED`/`CONTEXT_DEPENDENT`
< `SUPPORTED`) and states which way the engine leans.

## Stated limits of round 1

Carried in the report itself, not only here:

- **n = 9.** A rate over single digits has no usable confidence interval.
- **One reviewer**, so inter-rater reliability cannot be measured and reviewer
  idiosyncrasy cannot be separated from engine error.
- **The reviewer sees the extractor's labels.** An effect recorded as
  `decreased` is the extractor's reading, so an extraction error can propagate
  into an *apparent* agreement. The `extraction_disputed` flag is the only guard,
  and it depends on the reviewer noticing.
- **Not a pass mark.** A low rate is a finding. The disagreement log is the
  useful output in either direction.

## Prior, for calibration

Before this harness existed, four scientific judgement calls were put to the
domain reviewer explicitly. Three concerned classification policy and **two of
those three were corrected**:

| Call | Outcome |
| --- | --- |
| K145Q/M211I "coiled-coil" naming | Corrected to inter-domain/linker-region; no UniProt coiled-coil annotation exists |
| N65S `substrate_selective` | Corrected to a processivity/chain-elongation defect |
| SCA48 as a separate entity | Upheld |
| `self_ubiquitination` in the readout family | Removed before review |

So the measured prior on the authors' unreviewed judgement is poor, which is
precisely the argument for this harness rather than against it. The engine's
value is in making judgement visible and correctable, not in being right
unaided.
