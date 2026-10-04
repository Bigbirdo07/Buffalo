# Goal 3 audit — what remains unknown, and what would settle it?

- Commit `97d46adf5018` · [`data/goals/goal3_flagship.json`](../data/goals/goal3_flagship.json)
- Evidence depth `ABSTRACT_OR_DERIVED_SOURCE` · full-text review completed: **false**

## Why this experiment, and not one a model invented

Every object names its parent. The chain is machine-readable, so the question
"why did you propose this?" has an answer that is not "it seemed useful":

```
sources            PMID:21652633, PMID:19892702
  └─ relationship  relationship:46abfb23-533a8d87
      └─ bridge    bridge:46abfb23-533a8d87:v2  (v2, supersedes bridge:46abfb23-533a8d87)
          └─ gap   9e74e79e
              └─ experiment  3c4fd926
```

The gap derives from the **bridge**, not from the annotation that retrieved the
pair. A test asserts the gap question contains a bridge term and does *not*
contain the retrieval feature, and the gap cannot be constructed without a bridge
at all.

## What exactly do we not know?

> **Do Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease converge on a shared functional defect in chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) in disease-relevant models, measured by at least one identical primary functional readout applied to both disease models and matched controls under the same conditions?**

**The untested assumption.** The evidence establishes a molecular link between
the two diseases' proteins. Nothing establishes that the downstream functional
consequence is the same — which is precisely the assumption any transfer of a
model, assay or therapeutic strategy between the two would rest on.

**Why it matters.** The two diseases are reported to converge on this biology, but no study has applied one assay to both. Until that is done, every downstream decision -- whether a model, assay or therapeutic strategy developed for one disease is informative for the other -- rests on an assumption rather than a measurement. A negative answer is as valuable as a positive one: it would stop effort being spent transferring tools across a boundary they do not cross.

**What is known.** 2 corroborating primary findings (PMID:21652633, PMID:19892702) establish a direct molecular link. Refined from the supporting evidence's own primary findings. PMID:21652633: "This study demonstrates that laforin and malin are key regulators of HSF1 and that defects in the HSF1-mediated stress response pathway might underlie" PMID:21652633: "This study demonstrates that laforin and malin are key r

**What is missing.** A head-to-head functional comparison: both diseases' models assayed in parallel, same readout, same control, same laboratory.

**Search coverage.** Title/abstract co-mention; full-text corpora `NOT_STARTED`.
Absence of retrieved evidence is absence of indexed co-mention, not evidence
that no relationship exists.

## The experiment

*Research proposal requiring expert review.*

**Hypothesis A.** Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease disrupt chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) equivalently, so the same functional readout reports the same defect in both.

**Hypothesis B.** The diseases share the molecular interaction the evidence describes, and a broad process annotation, while diverging functionally downstream. Under this hypothesis the link is real but the mechanisms are not equivalent, and tools should not be transferred between the diseases on the strength of it.

| | |
| --- | --- |
| Model system | Patient-derived or engineered cellular models of each disease in a shared genetic background |
| Perturbation | A standardised cellular stress applied identically to every arm. The bridge describes stress-responsive biology, so a baseline-onl |
| Comparator | A single shared control run in the same experiment as both disease arms. Separate per-disease controls would make the arms incompa |
| Primary endpoint | Direction and magnitude of the chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) response to stre |

**Primary readout** — the single measurement that decides it:
> Functional response of CHIP-dependent stress response to the standardised stress, measured with one identical assay, timing and analysis framework across both disease arms and the shared control

**Secondary readouts** — context only, cannot decide the hypothesis:
- diGly assay reporting protein ubiquitination as a supporting molecular profile, interpreted only alongside the primary functional readout
- Recovery of the challenged cells after the stress is withdrawn

## What result supports, and what refutes

**Supports.** Both disease models show disruption of chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) in the same direction, of comparable magnitude, relative to the shared control. This supports functional equivalence at the measured step and makes tools developed for one disease worth testing in the other.

**Refutes.** The two disease models differ in the direction of the effect, or one shows no detectable disruption of chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) while the other does, or the magnitudes differ beyond the range seen between replicate clones of a single genotype. Any of these weakens the shared-mechanism hypothesis: the diseases would touch the same process without disrupting it equivalently, and tools should not be transferred between them on this basis.

The refutation clause is enforced in code, not convention: a proposal with no
refuting result, with indistinguishable outcomes, or with an empty primary
readout raises rather than being returned with a warning. A hypothesis that any
readout could rescue has nothing that could refute it.

**The experiment can downgrade the relationship.** A result showing opposite
directions or an absent effect in one arm moves the pair toward
`SHARED_CELLULAR_PROCESS_NON_EQUIVALENT` — the same class another candidate in
this run already occupies. The system is not built so that every outcome
preserves the current answer.

## Limitations, stated by the proposal itself

- A single readout at one timepoint cannot exclude equivalence that emerges, or disappears, over time.
- A negative result constrains equivalence at the measured step only and does not exclude shared biology elsewhere.
- Model systems may not reproduce the cell type where the diseases actually diverge.

## What this run cannot claim

The bridge rests on abstract-level typed annotations. Full text was not obtained
for either supporting paper: one is in Europe PMC without open access, the other
has no PMC record. A reviewer with journal access may reach a more specific
bridge, and the artifact records that rather than implying the papers were read.

