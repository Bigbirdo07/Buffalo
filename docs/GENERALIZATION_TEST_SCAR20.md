# Generalization test: second disease, second edge (SCAR20 / SNX14)

The question this test was built to answer: **do the refinement rules work on a
second, structurally different disease without being modified?** If each disease
needs bespoke rule changes, the system is a bespoke analysis wearing a pipeline
costume. If the rules hold and only the plumbing needs widening, it is an engine.

Reproduce with:

```bash
PYTHONPATH=backend/src .venv/bin/python scripts/refine_edge.py \
  data/refinement/scar20_snx14_autophagy --offline \
  --output data/refinement/scar20_snx14_autophagy/edge_refinement.json
```

- Disease: Autosomal Recessive Spinocerebellar Ataxia 20, `MONDO:0014601`
- Gene: SNX14 · Upstream commit: `b923d18f`
- Edge: `pathophysiology[1].downstream[0]` — *SNX14 Loss of Function → Impaired
  Autophagosome Clearance in Neural Progenitors*
- Chosen because it is a gene-dysfunction→cellular-consequence edge whose target
  node carries two curated `REFUTE` items, on a disease whose nodes are mostly
  `PROVISIONAL` (SCAR16's were mostly unannotated) and whose negative evidence
  sits on nodes rather than edges.

## Verdict

**The scientific rules generalized unchanged. The plumbing did not.**

Zero changes were made to the synthesis rules (A1–A7, E1–E5), the evidence
critic, the importer, the field audit or the citation validator. Five
infrastructure defects had to be fixed, four of them exposed by SCAR20 having
properties SCAR16 happened not to have.

Two rule paths that **never fired during SCAR16** fired here, which is the
strongest available evidence that they encode something real rather than
post-hoc fitting of one case:

- **A1** (no direct review → INSUFFICIENT_EVIDENCE), reached because a citation
  check failed rather than because evidence was absent.
- **E3** (one SUPPORTED claim, remainder INSUFFICIENT_EVIDENCE →
  PARTIALLY_SUPPORTED), a rule added during the SCAR16 work that SCAR16 itself
  never exercised.

## Result

```
Edge: SNX14 loss of function -> impaired autophagosome clearance in neural progenitors
Synthesized: PARTIALLY_SUPPORTED (rule E3)

ac1  LC3 flux slowed in patient neural progenitors         SUPPORTED             (A2)
ac2  autophagosome-lysosome fusion blocked                 INSUFFICIENT_EVIDENCE (A1)
ac3  autolysosome formation impaired                       INSUFFICIENT_EVIDENCE (A1)
ac4  clearance impaired in non-neural patient cells        INSUFFICIENT_EVIDENCE (A1)

Citation checks: 4 VERIFIED, 3 NOT_CHECKABLE, 0 SPAN_NOT_LOCATED
```

### What the decomposition revealed

The upstream claim is composite. "Impaired autophagosome clearance" bundles at
least four separately measurable sub-steps, and once separated, the apparent
conflict in the evidence largely dissolves:

| Sub-step | Evidence | Cell type | Direction |
| --- | --- | --- | --- |
| LC3 flux | PMID:25848753 | patient neural progenitors | slowed |
| autophagosome **formation** | PMID:25848753 | patient neural progenitors | **unchanged** |
| autophagosome–lysosome **fusion** | PMID:29635513 | HEK293 | unchanged |
| autolysosome **formation** | PMID:29635513 | patient fibroblasts | unchanged |

The support and the refutation measure **different sub-steps in different cell
types**. They are not contradictory. The supporting publication itself states
that autophagosome formation is unchanged, which localises the defect to a
clearance step rather than to initiation — a distinction the composite upstream
wording loses.

A further scoping axis is allele, not cell type: the PX-domain in-frame deletion
p.Ala603_Gly632del retains a normal Torin1 response, so allele identity may drive
the discordance as much as cell type does. Recorded as gap context (`s05`),
deliberately attached to no claim.

### Where the engine diverges from likely expert judgement

A domain expert would plausibly call this edge **CONTEXT_DEPENDENT**: supported in
neural progenitors, refuted for the fusion sub-step in non-neural systems. The
engine returned **PARTIALLY_SUPPORTED**, and the reason is not scientific — it is
that the refuting spans could not be verified, so the critic demoted them to
NEUTRAL and they could not set status.

The trace shows both steps explicitly:

```
readout='autophagosome_lysosome_fusion' effect=unchanged -> REFUTES;
span check NOT_CHECKABLE -> NEUTRAL, cannot be DIRECT
```

This is the designed behaviour and it is defensible — unverifiable evidence
should not move a conclusion — but it means **retrieval access changes the
answer**. That is a limitation to state plainly rather than a bug to hide: the
refutations remain recorded in the artifact as upstream-curated and unverified,
so a reviewer sees exactly what was discounted and why.

## Corpus-scale finding: the non-PMID blind spot

The three unverifiable items share a cause. Upstream wrote the reference as a
bare PMC URL, and the deterministic validator resolves PMIDs only.

Measured across all 3,289 entries:

| Reference form | Evidence items | Share |
| --- | --- | --- |
| PMID (checkable today) | 204,054 | 90.2% |
| **Not checkable today** | **22,052** | **9.8%** |
| ORPHA | 7,408 | |
| DOI | 5,677 | |
| bare URL | 5,349 | |
| clinicaltrials | 1,819 | |
| CGGV | 1,391 | |
| other (GEO, PPR, ICTRP, NCIT, CIViC, CGDS, STRCHIVE) | 408 | |

**About one in ten curated evidence items can never influence a synthesized
status under the current rules.** Not because the evidence is weak, but because
its identifier form has no resolver. The DOI case is the cheapest fix and alone
accounts for 5,677 items.

A related upstream data-quality issue: **the same publication is referenced two
ways inside this single entry** — as `PMID:29635513` on one node and as
`url:https://pmc.ncbi.nlm.nih.gov/articles/PMC5961352/` on another. The two
forms do not deduplicate, so one source can be double-counted as two independent
sources, or discounted in one place and accepted in another.

## Infrastructure defects this test exposed

Each was a case of SCAR16 having a convenient property that SCAR20 lacks.

1. **The runner was disease-specific.** `refine_edge.py` hardcoded UniProt
   accession `Q9UNE7` (CHIP) and five STUB1 literature queries. Any second
   disease would have silently inherited SCAR16's protein and SCAR16's coverage
   queries. Now read from the plan, and a plan without `coverage_queries` is
   rejected rather than defaulted.
2. **An external outage was fatal.** UniProt returned HTTP 503 during this run.
   The runner aborted. Protein-domain context is derived context, not evidence,
   so an outage now degrades to "no domains derived" plus a FAILED coverage row.
3. **Non-PMID references were unrepresentable in a plan.** The guard correctly
   refused my first plan, which declared a PMID where upstream has a URL. Plans
   may now declare `pmid: null` with a `resolved_pmid` for retrieval, while the
   citation check still reports the upstream form as unverifiable.
4. **Extraction assumed retrievable text.** Every SCAR16 span sat in an abstract
   or an open-access full text. SCAR20's decisive refutations are in a
   **non-open-access results section**. The locator mechanism copies a sentence
   from retrieved text, so a loose locator would have copied an unrelated
   abstract sentence and presented it as support — worse than failing. Added an
   explicit `span_from: "upstream_snippet"` path that takes the span from the
   upstream curator's own quotation and is reported as never independently
   located.
5. **The gap and experiment generator does not generalize at all.**
   `build_gap_and_experiment.py` hardcodes `TARGET_CLAIM = "ac4-interdomain-missense"`
   and contains bespoke SCAR16 prose for every field. It is a one-off writer, not
   an engine stage, and it was not run for SCAR20. This is the largest remaining
   gap between what the system claims and what it does.

## What this does and does not establish

**Establishes:** the synthesis and criticism rules are disease-independent. They
produced a defensible, fully traceable result on a disease with a different
mechanism class, different evidence topology, different cell-type scoping and a
different failure mode, with no rule modification. Two previously untested rule
paths fired correctly.

**Does not establish:** that the engine is automated. The extraction step was
again hand-authored, and the judgement embedded in it — deciding that "impaired
autophagosome clearance" decomposes into these four sub-steps — remains the
highest-value and least reproducible part of the system. n is now 2.

**Open question for expert review:** is `PARTIALLY_SUPPORTED` the right call when
the refuting evidence is credible but unverifiable, or should an unverifiable
upstream refutation be able to force `CONTEXT_DEPENDENT`? That is a policy
choice about how much to trust upstream curation, and it belongs to the
reviewer, not to the software.
