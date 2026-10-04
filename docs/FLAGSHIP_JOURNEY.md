# Flagship journey — from a broad annotation to one concrete action

Every step is an object with an id. Status is `AWAITING_EXPERT_SIGNOFF`
throughout; nothing here is a finding.

- Commit `46771e2a93f2` · [`data/flagship/flagship_journey.json`](../data/flagship/flagship_journey.json)

## The chain

```
retrieval feature:      protein ubiquitination
        ↓  judged, not trusted
retrieval validity:     INCORRECT_BUT_CONNECTION_REAL
        ↓  evidence read independently
MechanisticBridge v1:   chaperone, co-chaperone, ubiquitin ligase, CHIP
        ↓  targeted enrichment of the SAME evidence
MechanisticBridge v2:   chaperone, co-chaperone, ubiquitin ligase, CHIP, stress response, HSF1
        ↓
KnowledgeGap → Experiment → primary readout (+2 secondary)
        ↓
capabilities → assets → candidate teams → coordination check
        ↓
coverage map → topology → next action
```

Goal 2 detail: [`FLAGSHIP_GOAL2_REPORT.md`](FLAGSHIP_GOAL2_REPORT.md) ·
plain language: [`FLAGSHIP_FOR_PATIENT_GROUPS.md`](FLAGSHIP_FOR_PATIENT_GROUPS.md)

## 1 · Three levels, never collapsed

| Level | Content | Source |
| --- | --- | --- |
| **Found by** | `protein ubiquitination` | the annotation that surfaced the pair |
| **Supported by** | chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) | the evidence itself |
| **Tested** | functional convergence at that node under stress | the experiment |

Retrieval explains why the graph found the pair; the bridge explains why it
survived refinement. **The experiment follows the bridge.**

## 2 · Bridge refinement — v1 preserved, v2 supersedes

**Full text was NOT obtained: `false`.** One source is in
Europe PMC but not open access; the other has no PMC record. What was retrieved
is Europe PMC's *typed, section-tagged text-mined annotations* — a derived
source, not the article.

| | v1 | v2 |
| --- | --- | --- |
| Terms | chaperone, co-chaperone, ubiquitin ligase, CHIP | chaperone, co-chaperone, ubiquitin ligase, CHIP, stress response, HSF1 |
| Method | `mechanism-vocabulary-over-direct-evidence-v1` | `europepmc-typed-annotations-primary-role-v1` |

**Why v1 missed the new terms.** 2 additional term(s) supported by statements their own papers claim as primary findings, which the v1 derivation missed because it required a term to appear in more than one source. A single paper's demonstrated result is stronger evidence than a term repeated as background across two.

New terms and the exact spans that justify them:
- **stress response** — PMID:21652633 (Gene Disease Relationship, `PRIMARY_EXPERIMENTAL_RESULT`)
  > This study demonstrates that laforin and malin are key regulators of HSF1 and that defects in the HSF1-mediated stress response pathway might underlie some of the pathological symp
- **HSF1** — PMID:21652633 (Gene Disease Relationship, `PRIMARY_EXPERIMENTAL_RESULT`)
  > This study demonstrates that laforin and malin are key regulators of HSF1 and that defects in the HSF1-mediated stress response pathway might underlie some of the pathological symp

v1 is not edited. It is superseded by `bridge:46abfb23-533a8d87:v2`, which names
`bridge:46abfb23-533a8d87` as its parent.

## 3 · Knowledge gap — `9e74e79e`

> **Do Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease converge on a shared functional defect in chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) in disease-relevant models, measured by at least one identical primary functional readout applied to both disease models and matched controls under the same conditions?**

**What is missing.** A head-to-head functional comparison: both diseases' models assayed in parallel, same readout, same control, same laboratory.

**Search coverage.** Title/abstract co-mention; full-text corpora `NOT_STARTED`.
Absence of retrieved evidence is absence of indexed co-mention, not evidence
that no relationship exists.

## 4 · Experiment — `3c4fd926`

*Research proposal requiring expert review.*

**Hypothesis A.** Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease disrupt chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) equivalently, so the same functional readout reports the same defect in both.

**Hypothesis B.** The diseases share the molecular interaction the evidence describes, and a broad process annotation, while diverging functionally downstream. Under this hypothesis the link is real but the mechanisms are not equivalent, and tools should not be transferred between the diseases on the strength of it.

**Primary readout** — the one thing that decides the hypothesis:
> Functional response of chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) to the standardised stress, measured with one identical assay, timing and analysis framework across both disease arms and the shared control

**Secondary readouts** — context only, cannot decide the hypothesis:
1. diGly assay reporting protein ubiquitination as a supporting molecular profile, interpreted only alongside the primary functional readout
2. Recovery of the challenged cells after the stress is withdrawn

**If refuted.** The two disease models differ in the direction of the effect, or one shows no detectable disruption of chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) while the other does, or the magnitudes differ beyond the range seen between replicate clones of a single genotype. Any of these weakens the shared-mechanism hypothesis: the diseases would touch the same process without disrupting it equivalently, and tools should not be transferred between them on this basis.

`assert_falsifiable` rejects a proposal with no refuting result, with
indistinguishable outcomes, or with an empty primary readout — a hypothesis that
any readout could rescue has nothing that could refute it.

## 5 · Capability coverage — 1 of 4 covered

| Required capability | Candidate | Status | To verify |
| --- | --- | --- | --- |
| Functional assay reporting chaperone, co-chaperone,  | — | `MISSING` | A group demonstrating this capability. Absence h |
| iPSC maintenance | — | `MISSING` | A group demonstrating this capability. Absence h |
| clone-aware statistical analysis | — | `MISSING` | A group demonstrating this capability. Absence h |
| diGly enrichment proteomics | Angelo Poletti (PMID:41664196, 2026) | `CANDIDATE_IDENTIFIED` | Confirm the group still runs this assay, and tha |

Topology **`MULTI_PARTY_EXECUTABLE`** — no single group is expected to hold a
model of each disease *and* the assay. Multi-party is a topology, not a failure.

## 6 · Next action

**`NO_VERIFIED_COLLABORATOR_IDENTIFIED`.** Candidates are publication-derived leads;
their claims are `PLAUSIBLE` or `SUPPORTED`, never `VERIFIED`.

> Approach a group with a demonstrated functional assay for chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) and ask whether it can be applied in parallel to models of Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease against a shared control.

**To verify first.** That a cellular model exists for both diseases; that any
candidate still runs the assay; that both models can be cultured identically —
if they cannot, a difference is confounded by protocol rather than biology.

**Remaining uncertainty.** Supporting evidence for the relationship is limited in number and experimental context. Expert review should establish whether it justifies the experiment before anyone is contacted. The refinement rests on
abstract-level annotations, not full text, so a reviewer with journal access may
reach a more specific bridge than this run could.

