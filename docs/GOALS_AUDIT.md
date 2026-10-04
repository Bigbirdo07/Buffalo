> **SUPERSEDED.** This records the verdict taken before the flagship selector
> was replaced. The current verdict is in
> [`GOALS_AUDIT_FINAL.md`](GOALS_AUDIT_FINAL.md); where the two differ, that one
> is correct. Kept because the defects it describes, and the reasoning that
> found them, are the reason the selector changed.

# Goals audit — does the scientific chain actually work?

Run end to end on real data, from one disease to one next action. No goal is
marked demonstrated because code exists; each is marked from what the data did.

- Commit `97d46adf5018`
- [`GOAL1_AUDIT.md`](GOAL1_AUDIT.md) · [`GOAL3_AUDIT.md`](GOAL3_AUDIT.md) · [`GOAL2_AUDIT.md`](FLAGSHIP_GOAL2_REPORT.md) · [`MONARCH_DIFFERENTIATION.md`](MONARCH_DIFFERENTIATION.md)

## Completeness matrix

| Goal | Required question | System output | Evidence quality | Status |
| --- | --- | --- | --- | --- |
| **1** | Who shares our biology? | 8 neighbours evaluated from 60 retrieved; 6 excluded by identity or evidence, 4 rejected or downgraded, 2 survived | Curated mechanism data + typed literature evidence; every claim cites sources | **DEMONSTRATED** |
| **3** | What remains unknown, and what settles it? | One gap derived from the bridge, one falsifiable experiment with enforced refutation criteria, complete object lineage | Bridge rests on abstract-level annotations; full text not obtained | **PARTIALLY_DEMONSTRATED** |
| **2** | What useful work already exists? | 5 atomic capabilities searched independently; 4 with candidates, 1 unknown; 0 assets; 0 coordination opportunities; topology `MULTI_PARTY_EXECUTABLE` | Publication-derived, team-level, never verified; willingness never inferred | **PARTIALLY_DEMONSTRATED** |

## The chain, on real data

```
GOAL 1  ── Autosomal Recessive Spinocerebellar Ataxia 16
            ↓ 60 candidates retrieved
            ↓ identity checked BEFORE any mechanism claim
            ↓ ranks 1 and 2 excluded as the same allelic spectrum
            ↓ 4 rejected or downgraded on evidence
            └─ 2 independent corroborated relationships

GOAL 3  ── validated relationship
            ↓ mechanistic bridge v2, derived from evidence not annotation
            ↓ knowledge gap 9e74e79e
            └─ experiment 3c4fd926, refutation enforced in code

GOAL 2  ── experiment requirements
            ↓ 5 atomic capabilities, each searched alone
            ↓ 4 covered / 1 unknown / 0 assets / 0 coordination
            └─ NO_VERIFIED_COLLABORATOR_IDENTIFIED, one first-contact question
```

## Goal 1 — DEMONSTRATED

Starting from a disease rather than a pair produced a genuinely mixed outcome:
two identity exclusions (**the two highest-ranked hits**), three rejections or
downgrades, one shared-process-only, and two surviving independent
relationships. 3 candidates were found for a reason that did not survive
while the connection did.

The audit earned its place: running eight candidates instead of four hand-picked
ones exposed two real defects — an acronym collision the pipeline had not
inherited from an earlier fix, and a mechanism claim with no nameable mechanism.
Both are fixed generally. Before the fix, six of eight were reported as sharing a
mechanism.

## Goal 3 — PARTIALLY_DEMONSTRATED

Everything structural works: the gap derives from the bridge and cannot be built
without one, the experiment has a single primary readout and an enforced
refutation condition, and the lineage from source to experiment is
machine-readable.

**What holds it back from DEMONSTRATED:** full text was not obtained for either
supporting paper. The bridge rests on typed abstract-level annotations, so a
reviewer with journal access may reach a different or more specific mechanism.
The experiment has not been reviewed by anyone qualified to say whether it is the
right experiment.

## Goal 2 — PARTIALLY_DEMONSTRATED

The search begins from experimental requirements rather than disease names, each
capability is searched independently, and evidence scope stays conservative
throughout.

**What holds it back:** no verified collaborator, no reusable asset located, one
capability unsearchable with available terms, and all capability evidence is
publication-derived — which shows a team did something once, not that they do it
now or would want to.

## Monarch differentiation

An association graph answers *what is connected to this disease*. On the flagship
pair this system answered: it was retrieved on **protein ubiquitination**, that reason
**did not survive the evidence**, the real basis is **chaperone, co-chaperone, ubiquitin ligase, CHIP**,
what remains unknown is whether the two converge functionally there, one
experiment would settle it, and 4 of 5 capabilities to run it have a published
candidate.

Full worked comparison in [`MONARCH_DIFFERENTIATION.md`](MONARCH_DIFFERENTIATION.md).
This project consumes Monarch data — DisMech is a Monarch Initiative project —
and adds a refinement layer on top of it, not a replacement for it.

## Biggest remaining scientific gap

**No qualified human has reviewed any of it.** The bridge, the gap, the
experiment and the candidate list are all `AWAITING_EXPERT_SIGNOFF`, and the
chain's weakest link is that its central mechanistic claim was read from
abstracts rather than papers. Everything downstream inherits that limit.

Second: the flagship selection rule ranks by corroboration count, which measures
how many papers co-mention two diseases rather than how well the mechanism is
understood. Under that rule a different pair now outranks the worked flagship;
the artifact records both rather than hiding the disagreement.

## Ready for UI?

**NO.**

The chain runs end to end and its invariants hold, but two of three goals are
partially demonstrated, and the limiting factor in both cases is evidence depth
and expert review — neither of which a UI addresses. Building an interface now
would present abstract-level, unreviewed conclusions with the confidence that a
finished product implies.

The shortest path to YES: expert review of the flagship bridge and experiment,
and full-text access for the two supporting papers.

