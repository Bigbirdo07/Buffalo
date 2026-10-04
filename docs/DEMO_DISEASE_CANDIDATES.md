# Demo disease candidates

Data-driven selection over all 3,289 real DisMech entries at commit
`b923d18f1c962eeaecf9f1f908305b21a8f26904`. Regenerate with
`scripts/audit_corpus.py` (metrics) and the PubMed queries recorded below.

- Per-disease metrics: [`data/audit/candidate_metrics.json`](../data/audit/candidate_metrics.json)
- PubMed activity: [`data/audit/pubmed_activity.json`](../data/audit/pubmed_activity.json)
- Snapshots: `data/audit/pubmed_snapshots/` (hash-verified, replayable offline)

**There is no composite score.** Each dimension is reported separately. Ranking
uses two visible, reproducible steps: (1) six named gates, (2) a count of how
many dimensions sit at or above the corpus 75th percentile. That count is a
tie-break aid, not a merit score, and it is shown alongside the raw dimensions so
a reviewer can disagree with the aggregation and still use the data.

## Step 1: gates

A candidate must satisfy all six. 33 of 3,289 entries do.

| Gate | Condition | Rationale |
| --- | --- | --- |
| Monogenic and Mendelian | 1–3 genes, `category` in {Mendelian, Genetic} | Allele-level reasoning needs a tractable gene set |
| Edge-level evidence | ≥80% of causal edges carry their own evidence | Edge evidence, not node evidence, is what gets refined |
| Variant and domain signal | ≥1 variant and ≥1 protein-domain mention | Required for domain/allele heterogeneity analysis |
| Model systems exist | ≥1 animal or experimental model | Needed for an actionable experiment |
| Recorded uncertainty | ≥2 across gaps, controversies, human/model mismatches, alternative hypotheses, REFUTE/NO_EVIDENCE items | A refinement cycle needs something genuinely unresolved |
| Mechanistic depth | longest causal chain ≥5 edges | Shallow taxonomies are not mechanism |

Corpus 75th-percentile thresholds used in step 2: causal edges 19, evidence items
47, longest chain 5, phenotypes 16, model-organism evidence 8, references 9,
protein-domain mentions 1, animal models 1, explicit gaps 2, human/model
mismatches 1, REFUTE/NO_EVIDENCE 1, upstream proposed experiments 1, subtypes 2.

## Step 2: top five candidates

Dimensions are raw counts from the importer. "p75 count" is the step-2 tie-break.

| Dimension | USP9X female | Wilson disease | BRPF1 ID | SCAR16 | Bachmann-Bupp |
| --- | --- | --- | --- | --- | --- |
| p75 count | 15 | 15 | 14 | 13 | 13 |
| Longest causal chain | 5 | 7 | 9 | **11** | 7 |
| Causal edges | 19 | **75** | 33 | 35 | 19 |
| Evidence items | 127 | **211** | 188 | 117 | 133 |
| REFUTE / NO_EVIDENCE items | 1 | 1 | 0 | **3** | 0 |
| Explicit gaps / controversies | **4** | 3 | 0 | 1 | 1 |
| Human/model mismatch discussions | 1 | 0 | 1 | 1 | 1 |
| Alternative or emerging hypotheses | 0 | **3** | 1 | 0 | 0 |
| Variants | 5 | 3 | 5 | **22** | 5 |
| Protein-domain mentions | 6 | 1 | 4 | **9** | 1 |
| Animal models | 3 | 0 | **8** | 6 | 2 |
| Experimental (non-animal) models | 0 | 3 | 7 | **12** | 3 |
| Model-organism evidence items | 37 | 28 | **77** | 51 | 20 |
| Upstream proposed experiments | **5** | 3 | 2 | 0 | 3 |
| References | 26 | **38** | 29 | 15 | 18 |
| PubMed total | 39 | 7,660 | 121 | 62 | 20 |
| PubMed since 2021 | 18 | 1,636 | 62 | 37 | 17 |

### 1. SCAR16 / STUB1 — recommended

- **Why scientifically interesting.** Deepest mechanism in the shortlist (11-edge
  causal chain) on a single gene, STUB1, encoding a dual-function co-chaperone
  and U-box E3 ligase. The entry carries 22 variants and the most domain-level
  detail (9 mentions), so allele- and domain-resolved reasoning is possible
  rather than aspirational.
- **Promising mechanistic uncertainty.** The upstream entry already records a
  REFUTE pointer stating that four of six assayed alleles were "not overtly
  different from WT CHIP" in ubiquitination activity, while the mechanism's first
  edge asserts loss of ligase activity for biallelic loss-of-function variants.
  That is a contradiction internal to the curated entry, at allele resolution.
- **Variant/subtype heterogeneity.** Yes, and it is the point: effects differ by
  domain (TPR, inter-domain linker, U-box) and by allele within a domain.
  The allelic dominant disorder SCA48 is curated separately, giving a clean
  cross-entity comparison.
- **Evidence sufficiency.** Yes. 117 evidence items, overwhelmingly PMID-backed,
  with open-access full text available for several of the decisive papers, so
  spans are deterministically verifiable rather than abstract-only.
- **Model systems.** Strongest in the shortlist: 12 experimental (non-animal)
  models plus 6 animal models, including patient fibroblasts, patient iPSC-derived
  cortical neurons, knock-in mouse and rat, and zebrafish.
- **Collaborator/asset discovery.** Likely. 62 publications with 37 since 2021 —
  an active but small field, and a patient-derived iPSC line is already published
  (PMID:29679845).

### 2. SCAR20 / SNX14 — recommended

- **Why scientifically interesting.** 20 pathophysiology nodes and a 7-edge chain
  for a lipid/autophagy gene whose mechanism is actively contested.
- **Promising mechanistic uncertainty.** The highest negative-evidence density in
  the entire shortlist: 10 REFUTE/NO_EVIDENCE items, including explicit findings
  that SNX14 loss did *not* impair autophagosome-lysosome fusion, did *not*
  change TAG levels, and that a candidate intervention failed to rescue
  cerebellar degeneration in mice. Negative results are curated, not hidden.
- **Variant/subtype heterogeneity.** 15 variants and 5 domain mentions.
- **Evidence sufficiency.** Yes — 116 evidence items.
- **Model systems.** 6 animal and 8 experimental models, including zebrafish and
  patient fibroblasts.
- **Collaborator/asset discovery.** Plausible: 45 publications, 20 since 2021.
  Smaller field than SCAR16, with correspondingly fewer potential partners.
- **Note.** It gates in but ranks lower on step 2 (12) than entries above; its
  distinguishing strength is contradiction density, which is exactly what an
  evidence-refinement engine should be tested against.

### 3. Bachmann-Bupp syndrome / ODC1 — recommended

- **Why scientifically interesting.** Ultra-rare gain-of-function ODC1 disorder
  where the molecular lesion (C-terminal truncation impairing degradation while
  preserving catalysis) is unusually crisp, and a mechanism-directed agent
  (eflornithine/DFMO) already exists.
- **Promising mechanistic uncertainty.** A documented human/model mismatch: the
  K6/ODC mouse reproduces the alopecia and predicted the DFMO response but is
  skin-restricted and develops tumours, so whether whole-body stabilised ODC
  behaves the same in patients is open. A second recorded gap asks whether
  earlier treatment initiation changes neurodevelopmental trajectory.
- **Variant/subtype heterogeneity.** 5 variants; limited domain-level detail (1).
- **Evidence sufficiency.** Yes — 133 evidence items on only 20 publications,
  i.e. unusually dense curation per paper.
- **Model systems.** 2 animal and 3 experimental models.
- **Collaborator/asset discovery.** Very likely despite small size: 20
  publications, 17 of them since 2021, indicating a small, active, concentrated
  community — the easiest of the five to enumerate exhaustively.

### 4. USP9X female-restricted syndromic intellectual disability — not recommended for the first cycle

- **Why scientifically interesting.** Highest count of explicit recorded gaps (4)
  plus a human/model mismatch, 6 domain mentions, and 5 upstream proposed
  experiments to build on. An X-linked, female-restricted deubiquitinase
  disorder.
- **Promising mechanistic uncertainty.** Genuinely deep questions: what modifies
  penetrance once skewed X-inactivation is excluded; why 45,X individuals with a
  single USP9X allele generally lack neurological features; whether ciliary
  USP9X loss drives the extra-neural malformations.
- **Variant/subtype heterogeneity.** 5 variants.
- **Evidence sufficiency.** Yes — 127 evidence items.
- **Model systems.** 3 animal models but **no** non-animal experimental models,
  and the key signalling evidence comes from male partial-loss-of-function cells
  and Usp9x-null mice rather than female patient cells.
- **Collaborator/asset discovery.** Likely; 39 publications, 18 since 2021.
- **Why deferred.** Its central uncertainties are about penetrance, dosage and
  X-inactivation — population- and genotype-level questions. They are excellent
  science but a poor first test of an *edge-level, allele-resolved* refinement
  engine, and the missing human female cell models make an actionable first
  experiment harder to specify.

### 5. Wilson disease / ATP7B — not recommended for the first cycle

- **Why scientifically interesting.** Largest and richest mechanism in the
  shortlist: 75 causal edges, 211 evidence items, 6 mechanistic hypotheses
  including 3 explicitly EMERGING (cuproptosis, ferroptosis superimposition,
  liver-brain axis).
- **Promising mechanistic uncertainty.** Three well-posed gaps on whether
  cuproptosis occurs in human liver versus being a model-system proxy, the
  balance of direct brain copper deposition against liver-derived
  neuroinflammation, and whether the iron-dependent injury is true ferroptosis.
- **Variant/subtype heterogeneity.** Only 3 variants and 1 domain mention
  recorded, despite ATP7B being highly allelically heterogeneous — so the entry
  does not currently support allele-level work.
- **Evidence sufficiency.** Yes, abundantly.
- **Model systems.** 3 experimental models, no animal models recorded.
- **Collaborator/asset discovery.** Easy but unhelpfully large: 7,660
  publications, 1,636 since 2021.
- **Why deferred.** It is not a neglected rare disease by research activity —
  two orders of magnitude more literature than the others — so a refinement
  result is more likely to restate established knowledge, and the retrieval
  surface is large enough to make search-coverage claims weak.

## Recommended for human review

1. **SCAR16 / STUB1** — deepest mechanism, richest allele/domain detail, best
   model coverage, and an allele-resolved contradiction already present in the
   upstream entry.
2. **SCAR20 / SNX14** — highest curated negative-evidence density in the corpus.
3. **Bachmann-Bupp / ODC1** — crisp gain-of-function lesion, explicit
   human/model mismatch, smallest and most enumerable community.

This ranking departs from the step-2 count, which favours USP9X and Wilson
disease, and the reason is stated rather than absorbed into a score: the first
refinement cycle targets **edge-level, allele-resolved mechanism**, so the
variant/domain and model-system dimensions are weighted above raw edge and
evidence volume, and very high research activity counts against a candidate for
a rare-disease demonstration. A reviewer who weights volume differently should
read the table above and reach USP9X or Wilson disease instead; the data supports
that disagreement.

No disease is hard-coded as the winner. SCAR16 was used for the first refinement
cycle (`data/refinement/scar16_stub1_e3/`, documented in
[`REAL_IMPORT_AUDIT.md`](REAL_IMPORT_AUDIT.md)) because it ranked first on the
criteria above, and that selection remains open to revision.

## PubMed activity query metadata

Reproducible via NCBI ESearch, retrieved 2026-10-03, cached under
`data/audit/pubmed_snapshots/`. Each candidate has a total and a `2021:2026[dp]`
count. Queries are deliberately gene/disease-term based and are not exhaustive
field surveys; they index activity, not evidence.

| Candidate | Query |
| --- | --- |
| SCAR16 | `(STUB1[tiab] OR "CHIP"[ti]) AND (SCAR16[tiab] OR "spinocerebellar ataxia"[tiab] OR "Gordon Holmes"[tiab])` |
| SCAR20 | `SNX14[tiab] OR SCAR20[tiab]` |
| Bachmann-Bupp | `"Bachmann-Bupp"[tiab] OR (ODC1[tiab] AND (neurodevelopmental[tiab] OR alopecia[tiab]))` |
| USP9X female | `USP9X[tiab] AND (intellectual disability[tiab] OR neurodevelopmental[tiab])` |
| BRPF1 ID | `BRPF1[tiab]` |
| Wilson disease | `"Wilson disease"[tiab] OR "Wilson's disease"[tiab]` |
| Tangier disease | `"Tangier disease"[tiab]` |
| Apert syndrome | `"Apert syndrome"[tiab]` |
| MEDS / IER3IP1 | `IER3IP1[tiab] OR MEDS syndrome[tiab]` |
| VRK1 neuronopathy | `VRK1[tiab] AND (motor neuron[tiab] OR neuronopathy[tiab] OR ataxia[tiab])` |
| BCKDK deficiency | `BCKDK[tiab]` |

## Limits of this selection

- The gates use counts from the upstream entry, so a disease with a shallow
  DisMech entry but deep real-world literature is excluded by curation depth, not
  by biology.
- `protein_domain_mentions` is a substring heuristic over the entry's JSON, not a
  parsed domain model; it indicates where domain reasoning is *possible*.
- PubMed counts measure publication volume, not evidence quality or availability.
- Candidate metrics do not assess whether the mechanism is correct — only how
  much structured, evidenced mechanism is present to refine.
