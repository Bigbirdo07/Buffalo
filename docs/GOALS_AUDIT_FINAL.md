# Goals audit — final

Supersedes [`GOALS_AUDIT.md`](GOALS_AUDIT.md), which recorded an earlier verdict
taken before the flagship selector was replaced. Where the two differ, this
document is current.

- Commit `d2ee675c2e20` · UI contract [`data/demo/flagship_story.json`](../data/demo/flagship_story.json)
- Machine-readable verdict: [`data/demo/goals_summary.json`](../data/demo/goals_summary.json)

## Three different questions, three different answers

The central distinction in this document: **what the system did**, **whether a
scientist has agreed with it**, and **whether the work could actually be
executed** are not the same question. Conflating them is how a prototype starts
implying approval it does not have.

| Goal | Question | Technical status | Scientific review | Execution readiness |
| --- | --- | --- | --- | --- |
| **1** | Who genuinely shares relevant biology? | **DEMONSTRATED** | n/a | n/a |
| **3** | What uncertainty should be tested next? | **DEMONSTRATED** | `AWAITING_EXPERT_SIGNOFF` | n/a |
| **2** | What useful work already exists? | **DEMONSTRATED** | n/a | `PARTIAL` |

**READY_FOR_UI: YES** — with expert signoff still pending, which is the correct
state for a research-support prototype.

## Goal 1 — DEMONSTRATED

8 of 60 retrieved neighbours evaluated; 6 excluded as the same entity under different names; 4 rejected or downgraded on evidence; 2 survived as independent corroborated relationships.

The outcome is selective rather than confirmatory, which is the only way this
goal can be demonstrated at all:

| Outcome | Candidates |
| --- | --- |
| Excluded as the same entity under another name | Spinocerebellar Ataxia 48, Cerebellar Ataxia-Hypogonadism Syndrome, Autosomal Dominant Cerebellar Ataxia Type I |
| Rejected or downgraded on evidence | Autosomal Dominant Cerebellar Ataxia Type I, Peroxisome Biogenesis Disorder 5B, Friedreich Ataxia, Fragile X-Associated Tremor Ataxia Syndrome |
| Survived as independent | Neurodevelopmental Disorder With or Without Autism or Seizures, Lafora_Disease |

The two highest-ranked retrieval hits were excluded. A system that reported them
as cross-disease discoveries would be reporting one disease under three names.

## Goal 3 — DEMONSTRATED technically, review pending

Gap derives from the evidence-backed bridge and cannot be built without one; experiment has one primary readout and an enforced refutation condition; lineage from source to experiment is machine-readable.

**The question:** Do Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease converge on a shared functional defect in chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) in disease-relevant models, measured by at least one identical primary functional readout applied to both disease models and matched controls under the same conditions?

**The bridge it derives from:** chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) (v1, superseding
None), read from PMID:21652633, PMID:19892702.

**Evidence status:** `PROVISIONALLY_SUPPORTED` · **review:** `AWAITING_EXPERT_SIGNOFF`

Technical demonstration means the system converted audited evidence into a
traceable gap and a structurally falsifiable experiment. It does **not** mean a
scientist has approved either.

## Goal 2 — DEMONSTRATED technically, execution partial

5 atomic capabilities derived from the frozen experiment and searched independently; 4 have supported candidates; 1 unknown; NO_RELEVANT_ASSET_IDENTIFIED; topology MULTI_PARTY_EXECUTABLE; willingness never inferred.

`NO_VERIFIED_COLLABORATOR_IDENTIFIED` does not mean this goal failed. The goal
asks what useful work already exists, not whether anyone has agreed to do it.
Willingness is `UNKNOWN` for every candidate and is never inferred.

| | |
| --- | --- |
| Capabilities with supported candidates | 4 |
| Capabilities missing or unknown | 1 |
| Reusable assets located | `NO_RELEVANT_ASSET_IDENTIFIED` |
| Coordination opportunities | 0 — none substantiated |
| Topology | `MULTI_PARTY_EXECUTABLE` |

## Flagship selection

| | |
| --- | --- |
| Starting disease | Autosomal Recessive Spinocerebellar Ataxia 16 |
| Automated first choice | Neurodevelopmental Disorder With or Without Autism or Seizures |
| Selected for the demo | **Lafora_Disease** |
| Operator override | **True** |

Interpretable components, mechanistic specificity weighted highest. Corroboration count is a weak tie-break at weight 0.03, because the number of papers co-mentioning two diseases measures attention, not mechanistic understanding.

The override is recorded rather than hidden: Selected for demonstration: this pair shows the retrieval-correction behaviour end to end (found through a broad annotation, that explanation rejected, a different evidence-backed bridge derived), and its relationship has been checked against primary literature independently. The automated ranking placed Neurodevelopmental Disorder With or Without Autism or Seizures first at 0.8056 against 0.748; that ranking is recorded above and is not overwritten.

## Differentiation, in one paragraph

Monarch and DisMech identify biomedical associations and disease mechanisms, and
this project consumes their data — every disease entry comes from DisMech, a
Monarch Initiative project. The Atlas adds a refinement-and-action layer on top:
it records *why* a candidate relationship was found, tests whether that
explanation survives evidence review, identifies the unresolved biological
assumption, proposes a falsifiable experiment, and maps what research capability
already exists to test it. On the flagship pair the retrieval explanation did not
survive, the connection did, and the system said so.

## Major limitations

1. **Full text was never obtained** for either supporting paper. One sits in
   Europe PMC without open access; the other has no PMC record. The central
   mechanistic claim was read from typed abstract-level annotations, and every
   downstream object inherits that limit.
2. **No qualified human has reviewed any of it.** Bridge, gap, experiment and
   candidate list are all `AWAITING_EXPERT_SIGNOFF`.
3. **No verified collaborator and no reusable asset.** Capability evidence shows
   a team did something once, not that they do it now or would want to.

## Why READY_FOR_UI is YES despite those

Goals 1-3 technically demonstrated on real data, expert review clearly labelled pending, missing information explicit, no medical recommendation, no willingness claimed, provenance and limitations present, UI contract stable and reproducible.

Expert review is pending, and the contract says so in the artifact the UI reads.
The limitations above are data in `flagship_story.json`, not caveats someone has
to remember to mention.

