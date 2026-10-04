# Flagship journey — one candidate connection to one next action

Every step is an object with an id, produced by the pipeline. The pair was
selected by evidence: it is the only retrieved relationship that is both an
independent cross-disease pair and corroborated by two primary findings.

**Status: `AWAITING_EXPERT_SIGNOFF` at every step.** Nothing here is a finding.

- Commit `f2561322748c` · pipeline `cross-disease-pipeline-v1` · synthesis `cross-disease-synthesis-v1`
- Machine-readable: [`data/flagship/flagship_journey.json`](../data/flagship/flagship_journey.json)

## The three levels, kept separate

This is the distinction the whole system turns on. Collapsing any two of these
is how a system ends up testing the wrong thing.

| Level | Content | Where it comes from |
| --- | --- | --- |
| **Found by** | `protein ubiquitination` | the annotation that surfaced the pair |
| **Supported by** | chaperone, co-chaperone, ubiquitin ligase, CHIP | the retrieved literature |
| **Tested** | functional convergence at that node under stress | the experiment below |

The first explains why the graph found the pair. The second explains why it
survived refinement. **They are not the same, and the experiment follows the
second.** A test built on the first would measure a process both diseases touch
while missing the step where they actually meet.

## 1 · Retrieval

**Autosomal Recessive Spinocerebellar Ataxia 16** → **Lafora Disease**

Retrieved on `SHARED_CELLULAR_PROCESS, SHARED_CELL_TYPE, PHENOTYPE_SIMILARITY`, strongest feature
*protein ubiquitination*. Trace `46abfb23-533a8d87`.

## 2 · Identity — checked before any mechanism claim

`DISTINCT_DISEASE`: two independent disease entities, so this is a real
cross-disease question rather than two names for one thing.

## 3 · The retrieval reason is judged, not trusted

`INCORRECT_BUT_CONNECTION_REAL`

The pair is real **and** the annotation that found it is not the explanation.
Both facts are recorded; neither overwrites the other.

## 4 · Validated mechanistic bridge — `bridge:46abfb23-533a8d87`

> Evidence establishing a direct link describes chaperone, co-chaperone, ubiquitin ligase. Regulators named across the evidence: CHIP. This is what the literature supports, and it is not the same as the annotation that retrieved the pair.

Derived from PMID:21652633, PMID:19892702 by
`mechanism-vocabulary-over-direct-evidence-v1` — read out of the evidence text, not inherited from
the annotation. Narrower than the retrieval feature: **True**.

## 5 · Knowledge gap — `e939ac76`

> **Do Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease converge on a shared functional defect in chaperone, co-chaperone and ubiquitin ligase biology (CHIP) in disease-relevant models, measured with a single shared readout under matched conditions?**

*Type* `missing_assay` · experimentally resolvable

**Why it matters.** The two diseases are reported to converge on this biology, but no study has applied one assay to both. Until that is done, every downstream decision -- whether a model, assay or therapeutic strategy developed for one disease is informative for the other -- rests on an assumption rather than a measurement. A negative answer is as valuable as a positive one: it would stop effort being spent transferring tools across a boundary they do not cross.

**What is known.** 2 corroborating primary findings (PMID:21652633, PMID:19892702) establish a direct molecular link. Evidence establishing a direct link describes chaperone, co-chaperone, ubiquitin ligase. Regulators named across the evidence: CHIP. This is what the literature supports, and it is not the same as the annotation that retrieved the pair. They do not establish that the downstream functional consequence is the same in both diseases, and the supporting reports are limited in number and experimental context.

**What is missing.** A head-to-head functional comparison: both diseases' models assayed in parallel, same readout, same control, same laboratory.

**Search coverage.** Title/abstract co-mention only; full-text corpora
`NOT_STARTED`. Absence of retrieved evidence is absence of indexed co-mention,
not evidence that no relationship exists.

## 6 · Experiment — `d3261c4d`

*Research proposal requiring expert review.*

**Hypothesis A.** Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease disrupt chaperone, co-chaperone and ubiquitin ligase biology (CHIP) equivalently, so the same functional readout reports the same defect in both.

**Hypothesis B (competing).** The diseases share the molecular interaction the evidence describes, and a broad process annotation, while diverging functionally downstream. Under this hypothesis the link is real but the mechanisms are not equivalent, and tools should not be transferred between the diseases on the strength of it.

| | |
| --- | --- |
| Model system | Patient-derived or engineered cellular models of each disease in a shared genetic background |
| Perturbation | A standardised cellular stress applied identically to every arm. The bridge describes stress-responsive biology, so a baseline-only comparison could miss a defect that appears only when the pathway is challenged, and a null result would then be uninterpretable. |
| Comparator | A single shared control run in the same experiment as both disease arms. Separate per-disease controls would make the arms incomparable, which is the failure this design exists to avoid. |
| Primary endpoint | Direction and magnitude of the chaperone, co-chaperone and ubiquitin ligase biology (CHIP) response to stress in each disease arm relative to the shared control. |

**Readouts** — primary functional, supporting molecular:
1. Functional response of chaperone, co-chaperone and ubiquitin ligase biology (CHIP) to the standardised stress, measured identically in every arm
2. diGly assay reporting protein ubiquitination as a supporting molecular profile, interpreted only alongside the primary functional readout

**If supported.** Both disease models show disruption of chaperone, co-chaperone and ubiquitin ligase biology (CHIP) in the same direction, of comparable magnitude, relative to the shared control. This supports functional equivalence at the measured step and makes tools developed for one disease worth testing in the other.

**If refuted.** The two disease models differ in the direction of the effect, or one shows no detectable disruption of chaperone, co-chaperone and ubiquitin ligase biology (CHIP) while the other does, or the magnitudes differ beyond the range seen between replicate clones of a single genotype. Any of these weakens the shared-mechanism hypothesis: the diseases would touch the same process without disrupting it equivalently, and tools should not be transferred between them on this basis.

The refutation clause is enforced: `assert_falsifiable` raises if a proposal
states no refuting result, if the two outcomes cannot be distinguished, or if it
lacks a comparator or readout. A result can therefore downgrade the relationship
rather than only confirm it.

## 7 · Capability coverage — 1 covered, 3 missing

| Required capability | Candidate | Evidence scope | Status | To verify |
| --- | --- | --- | --- | --- |
| Functional assay reporting chaperone, co-chaperone and ubi | — | No candidate retrieved by the recorded searches. | `MISSING` | A group demonstrating this capability. Absence here means  |
| iPSC maintenance | — | No candidate retrieved by the recorded searches. | `MISSING` | A group demonstrating this capability. Absence here means  |
| clone-aware statistical analysis | — | No candidate retrieved by the recorded searches. | `MISSING` | A group demonstrating this capability. Absence here means  |
| diGly enrichment proteomics | Angelo Poletti (PMID:41664196, 2026) | Publication shows the technique was performed by this team a | `CANDIDATE_IDENTIFIED` | Confirm the group still runs this assay, and that it can b |

Topology: **`MULTI_PARTY_EXECUTABLE`**. No single group is expected to hold a
model of each disease *and* the assay; multi-party is a topology, not a failure.

## 8 · What a patient organization should do next

**`NO_VERIFIED_COLLABORATOR_IDENTIFIED`.** The candidates are leads from publications;
their capability claims are `PLAUSIBLE` or `SUPPORTED`, never `VERIFIED`.

> Approach a group with a demonstrated functional assay for chaperone, co-chaperone and ubiquitin ligase biology (CHIP) and ask whether it can be applied in parallel to models of Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease against a shared control.

**The specific unresolved question.** Do Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease converge on a shared functional defect in chaperone, co-chaperone and ubiquitin ligase biology (CHIP) in disease-relevant models, measured with a single shared readout under matched conditions?

**What would answer it.** The experiment above: both disease models and one
shared control, challenged identically, one functional readout.

**What appears useful already.** One of four required capabilities has a
published candidate. Three do not.

**What to verify first.** That a cellular model exists for both diseases; that
any candidate group still runs the assay; and that both models can be cultured
identically — if they cannot, a difference is confounded by protocol.

**Who to approach.** No named party is sufficiently supported. The category to
approach is a group with a demonstrated functional assay for
chaperone, co-chaperone, ubiquitin ligase, able to run it across both diseases.

**Remaining uncertainty.** Supporting evidence for the relationship is limited in number and experimental context. Expert review should establish whether it justifies the experiment before anyone is contacted.

