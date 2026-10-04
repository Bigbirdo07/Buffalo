# Expert review packet — SCAR16 × Lafora Disease

Everything a reviewer needs to accept, revise or reject this hypothesis, with
the spans it rests on. Generated from the system's own objects; no prose was
written for this document that is not traceable to one of them.

**This is a machine-generated research hypothesis. It is not an established
mechanism and not a medical recommendation.**

- Commit `d2ee675c2e20` · bridge `bridge:46abfb23-533a8d87` v1
- Evidence depth: **`ABSTRACT_OR_DERIVED_SOURCE`** · full text reviewed: **false**

---

## 1 · The claim, stated as narrowly as the evidence allows

**What the system does NOT claim:** that these two diseases have the same
mechanism.

**What it does claim:** evidence supports a shared downstream biological
hypothesis that remains experimentally unresolved.

| | |
| --- | --- |
| Found by | `protein ubiquitination` — a broad annotation |
| Was that the real reason? | **`INCORRECT_BUT_CONNECTION_REAL`** |
| Evidence-backed bridge | chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) |
| Relationship class | `SHARED_DOWNSTREAM_MECHANISM` |
| Identity | `DISTINCT_DISEASE` — two distinct diseases |

### Review question 1
Is the retrieval-level annotation correctly judged *not* to be the explanation?

☐ AGREE  ☐ DISAGREE  ☐ UNSURE — comment: ______________________

---

## 2 · The evidence, with spans

Supporting: PMID:21652633, PMID:19892702

Bridge terms and the statements they were read from:

**stress response** — PMID:21652633 · `Gene Disease Relationship` · `PRIMARY_EXPERIMENTAL_RESULT` · section: Abstract

> This study demonstrates that laforin and malin are key regulators of HSF1 and that defects in the HSF1-mediated stress response pathway might underlie some of the pathological symptoms in LD.

**HSF1** — PMID:21652633 · `Gene Disease Relationship` · `PRIMARY_EXPERIMENTAL_RESULT` · section: Abstract

> This study demonstrates that laforin and malin are key regulators of HSF1 and that defects in the HSF1-mediated stress response pathway might underlie some of the pathological symptoms in LD.

**chaperone** — PMID:19892702 · `Gene Function` · `PRIMARY_EXPERIMENTAL_RESULT` · section: Abstract

> Finally, we demonstrate that the co-chaperone carboxyl terminus of the Hsc70-interacting protein (CHIP) stabilizes malin by modulating the activity of Hsp70.

**co-chaperone** — PMID:19892702 · `Gene Function` · `PRIMARY_EXPERIMENTAL_RESULT` · section: Abstract

> Finally, we demonstrate that the co-chaperone carboxyl terminus of the Hsc70-interacting protein (CHIP) stabilizes malin by modulating the activity of Hsp70.

**CHIP** — PMID:19892702 · `Gene Function` · `PRIMARY_EXPERIMENTAL_RESULT` · section: Abstract

> Finally, we demonstrate that the co-chaperone carboxyl terminus of the Hsc70-interacting protein (CHIP) stabilizes malin by modulating the activity of Hsp70.


Only statements a paper claims as its own finding were allowed to contribute. A
sentence with no assertion language was treated as background.

### Review question 2
Do these spans support the bridge as stated, at this level of specificity?

☐ ACCEPT  ☐ REVISE to: ______________________  ☐ REJECT

---

## 3 · The unresolved assumption

> **Do Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease converge on a shared functional defect in chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) in disease-relevant models, measured by at least one identical primary functional readout applied to both disease models and matched controls under the same conditions?**

**Why it matters.** The two diseases are reported to converge on this biology, but no study has applied one assay to both. Until that is done, every downstream decision -- whether a model, assay or therapeutic strategy developed for one disease is informative for the other -- rests on an assumption rather than a measurement. A negative answer is as valuable as a positive one: it would stop effort being spent transfer

**What is missing.** A head-to-head functional comparison: both diseases' models assayed in parallel, same readout, same control, same laboratory.

### Review question 3
Is this the most important unresolved assumption, or is there a prior one?

☐ CORRECT  ☐ A PRIOR QUESTION EXISTS: ______________________

---

## 4 · The proposed experiment

**Hypothesis A.** Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease disrupt chaperone, co-chaperone and ubiquitin ligase biology (CHIP) equivalently, so the same functional readout reports the same defect in both.

**Hypothesis B.** The diseases share the molecular interaction the evidence describes, and a broad process annotation, while diverging functionally downstream. Under this hypothesis the link is real but the mechanisms are not equivalent, and tools should not be transferred between the diseases on the strength of it.

| | |
| --- | --- |
| Models | Patient-derived or engineered cellular models of each disease in a shared genetic background |
| Comparator | A single shared control run in the same experiment as both disease arms. Separate per-disease controls would make the arms incomparable, which is the  |
| Primary readout | Functional response of CHIP-dependent stress response to the standardised stress, measured with one identical assay, timing and analysis framework across both disease arms and the shared control |

**Supports if:** Both disease models show disruption of chaperone, co-chaperone and ubiquitin ligase biology (CHIP) in the same direction, of comparable magnitude, relative to the shared control. This supports functional equivalence at the measured step and makes tools developed for one disease worth testing in the 

**Refutes if:** The two disease models differ in the direction of the effect, or one shows no detectable disruption of chaperone, co-chaperone and ubiquitin ligase biology (CHIP) while the other does, or the magnitudes differ beyond the range seen between replicate clones of a single genotype. Any of these weakens the shared-mechanism hypothesis: the diseases would touch th

**Stated limitations:**
- A single readout at one timepoint cannot exclude equivalence that emerges, or disappears, over time.
- A negative result constrains equivalence at the measured step only and does not exclude shared biology elsewhere.
- Model systems may not reproduce the cell type where the diseases actually diverge.

### Review question 4
Could this experiment distinguish A from B as designed?

☐ YES  ☐ NO — the design would need: ______________________

### Review question 5
Is the primary readout the right one for this bridge?

☐ YES  ☐ NO — prefer: ______________________

---

## 5 · Known limitations of this synthesis

1. Full text was not obtained for either supporting paper: one is in Europe PMC without open access, the other has no PMC record.
2. The bridge rests on typed, section-tagged literature annotations covering title and abstract, not the full articles.
3. No direct cross-disease functional experiment has been performed or located.
4. Supporting evidence is concentrated in a small number of reports.

The most consequential is the first: **nobody read the full papers.** A reviewer
with journal access may reach a different or more specific bridge, and that
would change everything downstream.

---

## 6 · Overall

☐ **ACCEPT** — proceed to seek capability for this experiment as designed

☐ **REVISE** — the hypothesis or experiment needs the changes noted above

☐ **REJECT** — this is not worth pursuing, because: ______________________

Reviewer: ______________  Date: __________

Returning this packet moves the flagship from `PROVISIONAL_MACHINE_SYNTHESIS`
to `EXPERT_REVIEWED`, `EXPERT_REVISED` or `EXPERT_REJECTED`. All three are
useful outcomes; a rejection with a reason is a better result than an
unreviewed acceptance.

