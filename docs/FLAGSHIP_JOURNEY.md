# Flagship journey — one candidate connection to one next action

Every step below is an object with an id, produced by the pipeline rather than
written by hand. The pair was selected by evidence: it is the only retrieved
relationship that is both an independent cross-disease pair and corroborated by
two or more primary findings.

**Status: `AWAITING_EXPERT_SIGNOFF` at every step.** Nothing here is a finding.

- Software commit: `d8b28500de29`
- Pipeline: `cross-disease-pipeline-v1` · synthesis `cross-disease-synthesis-v1`
- Machine-readable: [`data/flagship/flagship_journey.json`](../data/flagship/flagship_journey.json)

## 1 · Disease A → candidate Disease B

**Autosomal Recessive Spinocerebellar Ataxia 16** → **Lafora Disease**

Retrieved on `SHARED_CELLULAR_PROCESS, SHARED_CELL_TYPE, PHENOTYPE_SIMILARITY`, strongest feature
*protein ubiquitination*. Decision trace `46abfb23-533a8d87`.

## 2 · Identity check — run before any mechanism claim

`DISTINCT_DISEASE` — two independent disease entities, so a relationship
between them is a genuine cross-disease question rather than two names for one
thing. (The same check classifies a different candidate in this run as a
subtype relationship and excludes it from discovery counts.)

## 3 · Validated relationship

`SHARED_DOWNSTREAM_MECHANISM` · retrieval validity **`INCORRECT_BUT_CONNECTION_REAL`**

> 2 independent primary findings establish a direct molecular link between the two diseases' proteins or processes, independent of the annotation that retrieved the pair.

**This is the case the architecture was rebuilt for.** The pair was retrieved on
a shared *protein ubiquitination* annotation, and that annotation is not why the
pair is real — the two proteins act on different substrate classes. The system
records both facts at once: the connection holds, the stated reason for finding
it was wrong.

Supporting evidence, retrieved blind: PMID:21652633, PMID:19892702

Alternatives that still apply: GENERIC_PHENOTYPE_OVERLAP, SHARED_TISSUE_DIFFERENT_BIOLOGY, BROAD_ONTOLOGY_ANNOTATION

## 4 · The critical difference

That equivalence at this step implies a shared treatment response.

Molecular anchor: `SHARED_CELLULAR_PROCESS=WEAK`. Variant compatibility:
`UNKNOWN` — the two diseases have no shared gene, so the
relationship must stand on process-level evidence alone.

## 5 · Knowledge gap — `3888d7ae`

> **Do Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease produce equivalent functional disruption of protein ubiquitination in disease-relevant models, measured with a single shared readout?**

*Type:* `missing_assay` · *Resolvability:* experimentally resolvable

**Why it matters.** The two diseases are reported to converge on this biology, but no study has applied one assay to both. Until that is done, every downstream decision -- whether a model, assay or therapeutic strategy developed for one disease is informative for the other -- rests on an assumption rather than a measurement. A negative answer is as valuable as a positive one: it would stop effort being spent transferring tools across a boundary they do not cross.

**What is known.** 2 corroborating primary findings (PMID:21652633, PMID:19892702) establish a direct molecular link. They do not establish that the downstream functional consequence is the same in both diseases.

**What is missing.** A head-to-head functional comparison: both diseases' models assayed in parallel, same readout, same control, same laboratory.

**Search coverage.** Co-mention in title and abstract only; full-text corpora
`NOT_STARTED`. Absence of retrieved evidence is absence of indexed co-mention,
not evidence that no relationship exists.

## 6 · Experiment — `b5613e70`

*Research proposal requiring expert review.*

**Question.** Do Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease produce equivalent functional disruption of protein ubiquitination in disease-relevant models, measured with a single shared readout?

**Hypothesis.** Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease disrupt protein ubiquitination equivalently, so the same functional readout reports the same defect in both.

**Competing hypothesis.** The two diseases engage the process through different branches, so the molecular link is real while the functional consequences differ in direction, magnitude or timing.

| | |
| --- | --- |
| Model system | Patient-derived or engineered cellular models of each disease in a shared genetic background |
| Comparator | A single shared control run in the same experiment as both disease arms. Separate per-disease controls would make the arms incomparable, which is the failure this design exists to avoid. |
| Primary readout | diGly assay reporting protein ubiquitination |
| Primary endpoint | Direction and magnitude of change in diGly assay reporting protein ubiquitination in each disease arm relative to the shared control. |

**If the hypothesis is supported.** Both disease models show disruption of protein ubiquitination in the same direction, of comparable magnitude, relative to the shared control. This supports functional equivalence at the measured step and makes tools developed for one disease worth testing in the other.

**If it is refuted.** The two disease models differ in the direction of the effect, or one shows no detectable disruption of protein ubiquitination while the other does, or the magnitudes differ beyond the range seen between replicate clones of a single genotype. Any of these weakens the shared-mechanism hypothesis: the diseases would touch the same process without disrupting it equivalently, and tools should not be transferred between them on this basis.

That refutation clause is checked, not decorative: the generator raises if an
experiment states no result that would weaken its hypothesis, or if the
supporting and refuting outcomes cannot be distinguished.

**Confounders.** Clone-to-clone variation can exceed the between-disease difference; the replicate-clone control exists to bound it. · Differing model maturity or culture age between arms can produce a difference unrelated to genotype. · If the two diseases' models cannot be cultured identically, any difference is confounded by protocol rather than biology.

**Limitations.** A single readout at one timepoint cannot exclude equivalence that emerges, or disappears, over time. · A negative result constrains equivalence at the measured step only and does not exclude shared biology elsewhere. · Model systems may not reproduce the cell type where the diseases actually diverge.

## 7 · Required capabilities and assets

Extracted from what the experiment declares, not inferred.

| Capability | Category |
| --- | --- |
| diGly enrichment proteomics | `proteomics` |
| iPSC maintenance | `cell_culture` |
| clone-aware statistical analysis | `statistical_analysis` |

Assets: 4 — a model of each disease, a shared
background-matched control, and reagents for the readout.

## 8 · Candidate capability holders

9 candidates from 7 targeted queries,
0 skipped. Every term was derived from the experiment; none was written as a
literal.

| Capability | PMID | Year | Last author | Disease involvement |
| --- | --- | --- | --- | --- |
| `crispr_editing` | 41699918 | 2026 | Henry M Colecraft | not established |
| `crispr_editing` | 40027688 | 2025 | Yihong Ye | named |
| `crispr_editing` | 35675767 | 2022 | Xiaoyuan Song | named |
| `ipsc_neuronal_differentiation` | 40498018 | 2025 | Sigrid A Langhans | not established |
| `ipsc_neuronal_differentiation` | 41236144 | 2025 | Esther B E Becker | not established |
| `ipsc_neuronal_differentiation` | 38757586 | 2024 | Federico Salas-Lucia | not established |

Each candidate carries the same limitation: a publication shows a technique was
performed by that team at that time. It is **not** evidence of current activity,
availability, or willingness to collaborate, and capability claims derived from
them are capped at team level.

## 9 · What a patient organization should do next

**No verified collaborator has been identified.** The candidates above are leads
derived from publications, and the capability claims attached to them are
`PLAUSIBLE` or `SUPPORTED`, never `VERIFIED`.

The defensible next action is narrow:

> Ask a group that already runs diGly enrichment proteomics
> whether that assay can be applied in parallel to cellular models of both
> Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease against a shared
> background-matched control.

**Why this question.** The two diseases are linked by 2
corroborating primary findings at the molecular level, and by nothing at the
functional level. One assay run across both arms answers that, and a negative
answer is as useful as a positive one.

**What to verify first.** That a cellular model exists for both diseases; that
the candidate group is still running this assay; and that both models can be
cultured identically, since if they cannot, any difference is confounded by
protocol rather than biology.

**What remains uncertain.** The supporting evidence is concentrated in a small
number of reports. Expert review should establish whether it is independent
enough to justify the experiment before anyone is contacted.

