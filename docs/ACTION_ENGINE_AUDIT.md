# Action engine audit (Phase 4)

Every figure below is read out of generated artifacts, not estimated. Rebuild and
re-verify with:

```bash
PYTHONPATH=backend/src .venv/bin/python scripts/build_phase4_action.py --offline
make assurance        # rebuilds the Phase 3 then the Phase 4 manifest, failing closed
make check            # 212 tests, ruff, mypy
```

- Bundle: [`data/action/scar16_stub1_e3/`](../data/action/scar16_stub1_e3/)
- Manifest: `data/action/scar16_stub1_e3/reproducibility_manifest.json`
- As-of date: **2026-10-03**, taken from the newest cached snapshot retrieval
  time. No execution clock is used anywhere in the bundle, so two runs over the
  same cache are byte-identical.
- Offline rebuild: **PASS**, all 16 artifacts byte-identical.
- Snapshots: 7 new action-source snapshots, 45 Phase 3 snapshots reused, all
  hash-verified.

## Headline result

```
Collaboration status: MISSING_CAPABILITY
Required capabilities: 8     Evidenced: 6     Missing: 2
Capability claims: 17        VERIFIED: 0   SUPPORTED: 15   OUTDATED: 2
Candidate subjects: 14       2 disease-anchored teams + 12 technique candidates
Research assets: 3           VALIDATED_FOR_TARGET_CONTEXT: 0   REQUIRES_VALIDATION: 3
Postgres round-trip: PASS    71 artifacts, concurrency-safe
Human review: 3 reviewer decisions recorded; all generated objects PENDING
```

Targeted capability discovery closed four of the six gaps, including both of the
decisive ones. The result is still `MISSING_CAPABILITY`, and the character of the
evidence matters more than the count: twelve of the fourteen candidate subjects
were found by technique alone and have **no established STUB1 or SCAR16
involvement**, no verified current activity and no contact or availability check.
They are leads, not collaborators.

## Reviewer decisions on open scientific questions

Three classification questions the deterministic pipeline could not settle were
decided by the project's domain reviewer and recorded as append-only
`ScientificReview` records in
[`data/refinement/scar16_stub1_e3/scientific_reviews.json`](../data/refinement/scar16_stub1_e3/scientific_reviews.json),
also persisted to Postgres. The machine-produced value is preserved in
`original_value`; nothing was overwritten.

| Decision | Status | Effect |
| --- | --- | --- |
| p.Lys145Gln / p.Met211Ile class name | APPROVED_WITH_MODIFICATION | Canonical class is **inter-domain/linker-region missense**. "Coiled-coil" is retained only as attributed paper terminology; no UniProt-supported coiled-coil annotation is claimed, since Q9UNE7 annotates none at residues 145 and 211 |
| p.Asn65Ser effect label | APPROVED_WITH_MODIFICATION | **processivity / chain-elongation defect**, not `substrate_selective`. Mono-ubiquitination of Hsc70 with retained self-ubiquitination shows impaired chain elongation on one substrate; selectivity would need a comparative substrate experiment |
| SCA48 entity scope | APPROVED | SCA48 **stays a separate entity**. Its evidence may qualify SCAR16 claims through shared STUB1 biology but remains INDIRECT/QUALIFIES, never direct SCAR16 evidence |

Applying decisions 1 and 2 to the extraction inputs and re-running Phase 3 left
every atomic status unchanged (edge remains CONTEXT_DEPENDENT, rule E2); only the
claim wording and the effect label changed. The reviews record the superseded
values.

## Experiment used

- Experiment: `experiment:gap:59b75e11-a1e4-5dbb-8de6-4530b898c7d5:ac4-interdomain-missense`
- Knowledge gap: `gap:59b75e11-a1e4-5dbb-8de6-4530b898c7d5:ac4-interdomain-missense`
- Label, unchanged: `Research proposal requiring expert review.`
- Scientific question: whether STUB1 p.Lys145Gln and p.Met211Ile, which retain
  bulk recombinant E3 activity, impair substrate-selective or stress-dependent
  CHIP activity in disease-relevant human neurons.

Phase 3 artifacts were not modified for Phase 4. The Phase 3 `edge_refinement`,
`knowledge_gap` and `experiment_proposal` were regenerated once, for a schema
reason only: Phase 4 added fields to `SearchCoverage`, so the committed Phase 3
files no longer matched the current schema. A field-level diff confirmed every
status, rule, review, observation and citation check was byte-identical before
and after; the only changes were the new coverage fields taking their defaults.

## Extracted requirements

Eight capabilities and four assets, each traceable to the exact
`ExperimentProposal` field index it came from. Nothing was added that the
experiment does not state.

| Capability category | Canonical name | Source field |
| --- | --- | --- |
| `cell_culture` | iPSC maintenance | `required_capabilities[0]` |
| `crispr_editing` | STUB1 CRISPR editing | `required_capabilities[0]` |
| `isogenic_line_generation` | isogenic line generation | `required_capabilities[0]` |
| `ipsc_neuronal_differentiation` | iPSC neuronal differentiation | `required_capabilities[1]` |
| `ubiquitination_assay` | quantitative ubiquitination analysis | `required_capabilities[2]` |
| `proteomics` | diGly enrichment proteomics | `required_capabilities[2]` |
| `protein_biochemistry` | protein thermal-stability assay | `required_capabilities[3]` |
| `statistical_analysis` | clone-aware statistical analysis | `required_capabilities[4]` |

| Required asset | Source field |
| --- | --- |
| `neuronal_model`: iPSC line with a characterized parental background | `required_assets[0]` |
| `patient_derived_ipsc`: SCAR16 patient-derived iPSC line | `required_assets[1]` |
| `antibody`: validated CHIP and ubiquitin antibodies | `required_assets[2]` |
| `mass_spectrometry_access`: diGly-capable mass spectrometry | `required_assets[3]` |

Extraction decisions: one proposal field can yield several capabilities
(`required_capabilities[0]` yields iPSC maintenance, CRISPR editing and isogenic
line generation, because it names all three). Capability categories come from a
fixed enum, so an unmatched requirement would surface as `other` rather than be
dropped. 180 discovery queries were generated from these requirements, each
combining a requirement term with a gene, disease or mechanism context.

## Source coverage

| Source | Status | Hits | Queries | Snapshots |
| --- | --- | --- | --- | --- |
| PubMed | CHECKED | 48 records | 60 generated | 1 |
| NIH RePORTER | CHECKED | 214 hits → 35 distinct awards | 4 | 4 |
| ClinicalTrials.gov | CHECKED | 23 hits → 1 STUB1-listing study | 3 | 3 |
| Bright Data | **FAILED** | not obtained | 8 | 0 |
| Institutional web pages | **NOT_STARTED** | not obtained | 0 | 0 |
| NORD / Global Genes / Orphanet | **NOT_STARTED** | not obtained | 0 | 0 |
| Cell-line and plasmid repositories | **NOT_STARTED** | not obtained | 0 | 0 |

A failed or unattempted source carries no `result_count` at all, so it can never
be read as zero results; a test enforces this.

**Correction to the brief's premise.** The brief stated terminal DNS was
unavailable and instructed recording all live sources as FAILED. That is no
longer true in this environment: PubMed, NIH RePORTER, ClinicalTrials.gov and
rarediseases.org all responded. NIH RePORTER and ClinicalTrials.gov were
therefore genuinely searched rather than recorded as failures, which is why this
audit reports real grant and trial findings.

Bright Data remains genuinely unavailable: `BRIGHTDATA_API_TOKEN` and
`BRIGHTDATA_DATASET_ID` are not configured. It is recorded FAILED with that
reason, not as zero results, and its absence did not block the rest of the engine.

### PubMed, targeted capability queries

Seven queries executed, a deliberately small deduplicated subset of the 180
generated (about 4%). Running the full set would inflate apparent coverage
without adding evidence, since most combinations are redundant.

The queries are split into two tiers, because they answer different questions:

| Tier | Capability | Hits | What it establishes |
| --- | --- | --- | --- |
| A disease-anchored | crispr_editing | 4 | STUB1 locus has been edited in iPSC |
| A disease-anchored | proteomics | 1 | a STUB1 substrate ubiquitinome has essentially never been measured |
| B capability-anchored | crispr_editing | 22 | groups doing allele-specific endogenous editing in neuronal iPSC |
| B capability-anchored | isogenic_line_generation | 131 | groups building isogenic variant panels |
| B capability-anchored | proteomics | 11 | groups running neuronal diGly ubiquitinome proteomics |
| B capability-anchored | ipsc_neuronal_differentiation | 85 | groups differentiating iPSC to cerebellar/Purkinje-like neurons |
| B capability-anchored | statistical_analysis | **0** | see the limitation below |

**Why two tiers.** Tier A anchors on the gene or disease and is therefore nearly
empty by construction for an unmet requirement: it describes the experiment
nobody has run. `"STUB1" AND diGly/ubiquitinome` returns exactly one record, and
it is about myocilin, not ataxia. Tier B drops the gene and asks who can perform
the technique at all. Only Tier B can find a provider for a missing capability;
anchoring on the disease would only ever return people who already did the
experiment. Every Tier B candidate therefore carries an explicit statement that
no STUB1 or SCAR16 involvement was established.

**Decisive findings:**

- **Allele-specific STUB1 editing** — PMID:30605842 (2019), *"Generation of a
  homozygous CRISPR/Cas9-mediated knockout human iPSC line for STUB1"*, last
  author Stefan Hauser (DZNE Tübingen). The *same* group as the SCAR16 iPSC team
  has edited the STUB1 locus in iPSC. Important limit: it is a **knockout**, not
  an allele-specific point knock-in, so it evidences locus editing rather than
  the variant engineering the experiment requires.
- **Neuronal diGly ubiquitinome** — eleven groups, including PMID:33274322
  (2020) *"The ubiquitylome of developing cortical neurons"* (Stephanie L Gupton,
  UNC Chapel Hill — the same institution as the CHIP biochemistry team),
  PMID:34767452 (2021, MRC PPU Dundee), PMID:32142685 (2020, Harvard) and
  PMID:40480969 (2025, FLI Jena). Institutional adjacency to the CHIP team is a
  useful lead and is **not** converted into a capability claim for that team.

**Query-design limitation.** The `statistical_analysis` query returned zero hits.
That reflects the query, not the field: clone-level random-effects modelling is
routine practice and is rarely stated in a title or abstract in the terms used.
Zero hits here must not be read as an absence of capability. `iPSC maintenance`
likewise remains unmet only because its sole claim is the historical one from the
SCAR16 team; no capability-anchored query was written for it, as it is close to
universal in the field.

**Candidate selection.** Newest first, capped at three per capability, excluding
publications already represented by an existing team. Every retrieved PMID is
recorded in `capability_search.json`, so leads that were not promoted — Gupton's
UNC neuronal ubiquitylome among them — remain visible to a reviewer rather than
being silently discarded by the cap.

### PubMed, Phase 3 record set

48 cached records. Author names and affiliation strings for the candidate teams
are read out of these records; nothing about a person is typed into the code.
The 60 capability-specific PubMed queries were generated and recorded but not
separately executed: the record set was assembled during Phase 3 retrieval. That
is a real coverage gap — a targeted search for, say, "diGly proteomics" plus
"cerebellar neurons" has not been run, so a capable group outside the SCAR16
literature would not appear.

### NIH RePORTER

35 distinct awards retrieved; **0 used as capability evidence**. Every award's
disposition is recorded in `lineage.json`:

- `"STUB1 ataxia"` returned **no awards**. Stated precisely: no qualifying
  NIH-funded STUB1 ataxia project was identified in the NIH RePORTER snapshot
  using the recorded searches. That is a statement about this search, not about
  what exists; RePORTER also indexes US federal funding only.
- `CONTEXT_MISMATCH` — five JMJD1A prostate-cancer awards and two p53/aging
  awards genuinely discuss STUB1 or CHIP ubiquitination, but in oncology. Real
  mentions, wrong disease context.
- `SUBJECT_MISMATCH` — an active UCSF award (ends 2029) on the co-chaperone
  DNAJC7 in neurodegeneration and ataxia. Adjacent field, different gene;
  recorded as intelligence for a human reader, not as STUB1 capability.
- `RETRIEVED_BY_AMBIGUOUS_TOKEN` — awards matched only because "CHIP" collides
  with "ChIP" (chromatin immunoprecipitation) or because "neurodegeneration"
  appears as boilerplate.
- The single most topical award, a UNC Chapel Hill fellowship on the
  CHIP co-chaperone/E3 ligase, **ended in 2011**; its PI appears as an author on
  PMID:42567515.

The relevance rule is a strict conjunction: whole-word `STUB1` (case-sensitive,
so `ChIP` cannot match `CHIP`), a disease-specific context term, and an active
award. Nothing satisfies it. This was deliberately left strict after a looser
keyword filter admitted all seven oncology awards.

**Known limitation:** keyword matching cannot establish scientific relevance.
The rule is conservative in both directions — it excludes the 2011 UNC award,
which is topically the closest match, because its abstract says "nuclear stress
response" rather than "ataxia". A human reviewer should read the 35 retrieved
awards rather than trust the filter.

### ClinicalTrials.gov

23 hits, 1 relevant: **NCT01793168**, "Rare Disease Patient Registry & Natural
History Study" (Sanford Health), status RECRUITING. Its condition list includes
"Autosomal Recessive Cerebellar Ataxia Due to STUB1 Deficiency" explicitly, so
the relevance is specific rather than inferred from a generic rare-disease
listing. Recorded as a `registry` asset with
`reuse_status: REQUIRES_VALIDATION`.

Interpreted as clinical and registry infrastructure only. A test asserts that no
clinical study ID appears in any capability claim's evidence, so trial
participation cannot become mechanistic expertise.

### Patient organizations

**National Ataxia Foundation** is recorded as a `patient_organization`, evidenced
solely by its listing as a collaborator on the cached NCT01793168 record.

Deliberately *not* inferred: that it operates a STUB1 registry, funds STUB1
research, holds cohort access or connects patients to researchers. The registry
lists roughly 120 collaborating organizations and several hundred conditions, so
collaborator listing supports none of those specifics. `contact_source` states
that no direct contact route was verified. NORD, Global Genes and Orphanet were
reachable but were not ingested as web evidence in this run, so organization
coverage is `NOT_STARTED`.

## Candidates and their evidence

Both candidates are **publication-derived author groups**, modelled as
`Laboratory` records with `official_url: null`. No verified laboratory website
was located, and the brief's rule against inventing institutional facts means
none was invented. Institution strings are publication affiliations at time of
publication.

### Author group 1 — SCAR16 patient iPSC and neuronal models

- Evidence: PMID:29679845 (2018), PMID:33097556 (2020)
- Derived people: Stefanie Schuster, Stefan Hauser, S Schuster, L Schöls
- Affiliations as published: Hertie Institute for Clinical Brain Research,
  University of Tübingen; German Center for Neurodegenerative Diseases (DZNE)
- Claims: `cell_culture` → **OUTDATED**;
  `ipsc_neuronal_differentiation` → **OUTDATED**
- Both publications fall outside the five-year recency window relative to the
  as-of date, so the capability is classified historical. This is the group that
  made the SCAR16 patient iPSC line and showed the fibroblast-versus-neuron
  heat-shock discordance — directly relevant work, with no evidence of current
  activity.

### Author group 2 — CHIP variant biochemistry

- Evidence: PMID:31619515 (2019), PMID:42567515 (2026)
- Derived people: Sabrina C Madrigal, Selin Altinok, Jonathan C Schisler
- Affiliations as published: McAllister Heart Institute, University of North
  Carolina at Chapel Hill; UNC Department of Pharmacology
- Claims: `ubiquitination_assay` → **SUPPORTED**;
  `protein_biochemistry` → **SUPPORTED**
- Current (2026) publication evidence, but a single source type. `VERIFIED`
  requires two independent source types and is correctly not reached. This is
  the group whose domain-resolved SCA48 work the Phase 3 refinement used as
  cross-entity qualifying evidence.

### Historical versus current activity

| Group | Most recent evidence | Classification |
| --- | --- | --- |
| SCAR16 patient iPSC | 2020 | historical / OUTDATED |
| CHIP biochemistry | 2026 | current, single-source |

No institutional page, grant or profile was checked for either group, so current
affiliation and current activity are unverified for every named person. Each
`Researcher.role` states this explicitly.

### Entity resolution

One `POSSIBLE_DUPLICATE` recorded: `researcher:s-schuster` and
`researcher:stefanie-schuster`. PubMed abbreviates forenames inconsistently
between records, so these may be one person or two. The records are **not**
merged and no capability evidence is pooled across them; the ambiguity is left
for human review. Where two name forms appear on the same publication the
decision is `DISTINCT` instead.

## Asset qualification

| Asset | Type | Reuse status | Why not validated |
| --- | --- | --- | --- |
| STUB1 patient iPSC line (PMID:29679845) | `ipsc_line` | REQUIRES_VALIDATION | Patient genotype is not the K145Q/M211I alleles the experiment needs; availability unknown, no repository deposit located |
| Published CHIP functional-assay methods | `assay` | REQUIRES_VALIDATION | Recombinant/cellular readout, not neuronal diGly ubiquitinome; materials and transferability unverified |
| Rare Disease Patient Registry (NCT01793168) | `registry` | REQUIRES_VALIDATION | Registry infrastructure; enrolment terms and STUB1 participant availability unverified |

Nothing is marked `VALIDATED_FOR_TARGET_CONTEXT`, and a test enforces it. The
variant mismatch on the iPSC line is stated in the artifact itself, naming both
K145Q and M211I.

## Missing capabilities

Six of eight, exposed by name in `scientist_explanation.json` and
`collaboration_opportunity.json`:

1. `crispr_editing` — STUB1 CRISPR editing
2. `isogenic_line_generation` — isogenic line generation
3. `proteomics` — diGly enrichment proteomics
4. `statistical_analysis` — clone-aware statistical analysis
5. `cell_culture` — iPSC maintenance (evidence exists but is OUTDATED)
6. `ipsc_neuronal_differentiation` — (evidence exists but is OUTDATED)

An `OUTDATED` claim does not count as provided. The two genuinely unevidenced
capabilities — allele-specific endogenous editing and diGly ubiquitinome
proteomics — are precisely the two that distinguish this experiment from the
recombinant work that produced the knowledge gap.

## Duplication analysis

**NOT ASSESSED.** No `ResearchProgram` records were built, because institutional,
foundation and company program sources were not searched. No duplication or
coordination claim is made. The UCSF DNAJC7 award is the only adjacent-program
signal and is recorded as subject-mismatched, not as overlap.

## Language, geographic and structural biases

- **Language:** only English-indexed PubMed, RePORTER and ClinicalTrials.gov
  records were searched. Non-English institutional and organization sources were
  not.
- **Geography:** NIH RePORTER covers US federal funding only. The one candidate
  group with directly relevant iPSC experience is German, so the grant evidence
  is structurally incapable of showing its current funding. Absence of grant
  evidence for that group is an artifact of source choice, not a finding.
- **Literature-set bias:** candidates were drawn from the SCAR16/STUB1 reading
  list assembled in Phase 3. A group with the required editing or proteomics
  capability but no STUB1 publication cannot appear. This is the largest
  structural bias in the bundle.
- **Seniority bias:** the first/last-author rule surfaces first authors and
  senior authors and omits middle authors, who often hold the hands-on skill.
- **Registry breadth:** NCT01793168 is a multi-condition registry; its STUB1
  relevance is real but shallow.

## Human review status

`PENDING` on every generated object: required capabilities, required assets,
capability claims, research assets, entity-resolution decisions, the
collaboration opportunity, and the upstream knowledge gap and experiment.

The evidence critic, requirement extraction and capability verification are
**deterministic rule-based software**. No LLM adjudication took place — no model
API key is configured in this environment — and none of it is expert scientific
review. No person or institution was contacted; no capability was confirmed with
anyone named here.

## Persistence verification

Verified against **PostgreSQL 16.15** (local Homebrew server, not Docker — Docker
was unnecessary once a native server was found, and the compose file is only one
way to provision one):

- **71** real Phase 3 and Phase 4 artifacts saved and reloaded with lossless
  round-trips on Postgres.
- Idempotent re-save of identical content; different content under the same
  object/version refused as a domain error.
- Immutability is guaranteed by a database constraint,
  `UNIQUE (object_id, source_version)`, not only by the Python pre-check.
- Reviews are append-only; the three reviewer decisions are persisted.
- 16 lineage edges written and read back.
- Nested payloads survive the JSON column: a `KnowledgeGap`'s
  `search_coverage.sources` array reloads intact.

**A concurrency defect that only Postgres exposed.** `save_artifact` performed a
read-then-insert with no `IntegrityError` handling. Under eight concurrent
writers of *identical* content, seven received a raw
`psycopg.errors.UniqueViolation` instead of the idempotent success the contract
promises. SQLite's write serialisation hides this. The fix treats losing the
insert race as expected rather than exceptional: roll back, re-read the committed
row, return it when the content hash matches, and raise the domain error only for
genuinely different content. Re-verified: eight concurrent identical writers all
succeed with one row; six conflicting writers all receive `ValueError`.

Eight Postgres-dialect tests now run in the suite, skipped automatically when no
server is reachable so the default suite still needs no database.

**Remaining persistence gap:** no Alembic migration. The schema is created by
`create_schema`, which is adequate for a single-developer workspace but is not a
migration path.

## Graph projection
## Graph projection

`scripts/build_projection.py` emits `graph_projection.json`: 79 nodes and 62
relationships covering Claim, Evidence, KnowledgeGap, Experiment,
RequiredCapability, CapabilityClaim, Laboratory, Researcher, ResearchAsset,
Organization, Grant, ClinicalStudy and CollaborationOpportunity.

The projection is a pure function with no database driver, so it is rebuildable
by construction and Neo4j can never become the source of truth. Properties worth
noting:

- The relationship vocabulary is closed and enforced at construction: an attempt
  to create a `CAUSES` edge raises. Unsupported causality cannot be projected.
- A laboratory only ever `MAY_ADDRESS` an experiment; an asset only ever
  `MAY_REUSE`, carrying its `REQUIRES_VALIDATION` status as an edge property.
- `POSSIBLY_SAME_AS` carries the `POSSIBLE_DUPLICATE` status as an edge rather
  than merging the two researcher nodes.
- Evidence edges keep their role (`direct_refuting`, `background_only`, …), so
  the graph cannot flatten refuting or background-only evidence into support.
- Zero dangling relationships; the emitter refuses to write if any appear.

Not yet done: no Neo4j writer, because no Neo4j server is available in this
environment. The projection JSON is the replay input for one.

## Lineage verification

The full chain is recorded in `lineage.json` and asserted by tests:

```
DisMech curated claim
  → refined atomic claims (CONTEXT_DEPENDENT edge; ac4 INSUFFICIENT_EVIDENCE)
  → KnowledgeGap
  → ExperimentProposal
  → RequiredCapability / RequiredAsset   (traced to exact proposal field indices)
  → discovery queries
  → cached source records                (hash-verified snapshots)
  → CapabilityEvidenceSignal
  → CapabilityClaim
  → Laboratory / Researcher / ResearchAsset / Organization
  → CollaborationOpportunity             (MISSING_CAPABILITY)
```

Every capability claim resolves to source records with snapshot hashes, and the
Phase 4 manifest pins the Phase 3 input hashes, so the scientific chain and the
action chain are linked by content rather than by assertion.

## Remaining blockers

1. **Bright Data unavailable** — no token or dataset ID. Institutional-page
   verification, and therefore current-affiliation and current-activity checks,
   cannot be completed.
2. **No Alembic migration** — the schema is created directly, which is not a
   migration path. Postgres itself now verifies.
3. **No Neo4j writer** — the projection is emitted as JSON but never loaded,
   since no Neo4j server is available.
4. **Patient-organization pages not ingested** — reachable but not captured as
   web evidence through the verification flow.
5. **Repository sources not searched** — asset availability remains unknown.
6. **Candidate affiliations and current activity unverified** — twelve technique
   candidates come from a single publication each, with no institutional page,
   grant or profile check. The `statistical_analysis` query returned zero hits
   because of its wording, not because the capability is absent.
7. **No expert review yet** — every object stays `PENDING`.
8. **Not a git worktree** — the repository has no `.git`, so no commit or push
   can be verified. The brief's claim that commit `d626450` exists and awaits a
   push cannot be confirmed here; per-file implementation hashes in both
   manifests are the compensating control.

## Acceptance conditions

| # | Condition | Status |
| --- | --- | --- |
| 1 | SCAR16 ExperimentProposal loaded | ✅ |
| 2 | RequiredCapabilities generated | ✅ 8 |
| 3 | RequiredAssets generated | ✅ 4 |
| 4 | PubMed capability discovery | ✅ 7 targeted tiered queries executed; full set deliberately not run |
| 5 | NIH RePORTER searched or failure recorded | ✅ searched; 35 awards, 0 qualifying |
| 6 | ClinicalTrials.gov checked | ✅ searched; NCT01793168 |
| 7 | Patient-organization source checked | ⚠️ via the registry record only; org pages NOT_STARTED |
| 8 | Bright Data used or unavailability recorded | ✅ recorded FAILED with reason |
| 9 | At least one candidate identified | ✅ 14 candidate subjects (2 disease-anchored teams, 12 technique candidates) |
| 10 | Every capability claim has evidence | ✅ |
| 11 | At least one asset candidate | ✅ 3 |
| 12 | Asset relevance explicitly qualified | ✅ all REQUIRES_VALIDATION |
| 13 | Search coverage complete and honest | ✅ failures and non-attempts visible |
| 14 | CollaborationOpportunity generated | ✅ MISSING_CAPABILITY |
| 15 | Missing capabilities visible | ✅ 2, by name, with the reason each remains open |
| 16 | Human review supported | ✅ append-only; 3 reviewer decisions recorded and persisted |
| 17 | Patient-language output | ✅ |
| 18 | Scientist-level output | ✅ |
| 19 | Postgres persistence works | ✅ PostgreSQL 16.15; 71 artifacts, concurrency defect found and fixed |
| — | Neo4j kept a rebuildable projection | ✅ pure function, no writer yet |
| 20 | Complete lineage preserved | ✅ |
| 21 | Full tests pass | ✅ 234 |
| 22 | Ruff passes | ✅ |
| 23 | mypy passes | ✅ 61 files |
| 24 | Offline reproduction passes | ✅ byte-identical |
| 25 | No unsupported collaborator claim presented as fact | ✅ |

Phase 4 is **not yet complete**: condition 7 remains partial, since patient and
disease-organization pages were reachable but not ingested as web evidence
through the verification flow. Every other condition is met. The scientific
action chain works end to end, reproduces byte-identically offline, and is backed
by a real canonical store.

Outstanding work, in the reviewer's priority order: verify current affiliations
and active capability for the candidate groups (needs institutional pages),
ingest at least one patient-organization source through the web-evidence flow,
add the Neo4j writer, and build the minimal UI. Bright Data stays deferred until
credentials exist; it is no longer the limiting factor.
