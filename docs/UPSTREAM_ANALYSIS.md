# Upstream analysis

Analysis date: 2026-10-03. Upstream is consumed read-only. The observations
below are based on the live `main` branches and live Monarch v3 OpenAPI surface;
every import run must additionally record the exact DisMech commit supplied by
the operator.

## DisMech already provides

DisMech is a mechanism-first, LinkML-backed knowledge base whose source of truth
is one YAML document per disorder under `kb/disorders/`. Its current schema is
`src/dismech/schema/dismech.yaml`, not the illustrative schema in the build
brief.

The current disease object includes identity/mappings, aliases and parents,
subtypes, genetic and variant records, `pathophysiology`, phenotypes,
experimental and computational models, biochemical readouts, treatments,
mechanistic hypotheses, and discussions. Important concrete structures are:

- `Pathophysiology`: `name`, prose `description`, cell/anatomy/process/function
  descriptors, gene(s), pathways, subtypes, model context, node-level
  `evidence`, `mechanism_confidence`, `biological_scale`, and `downstream`.
- `CausalEdge`: string `target`, optional description, edge-specific evidence,
  `hypothesis_groups`, `causal_link_type`, and free-text intermediate mechanisms.
- `EvidenceItem`: `reference`, `reference_title`, `supports`, `directness`,
  `quote_role`, `evidence_source`, exact `snippet`, explanation, and images.
  Current polarity values are `SUPPORT`, `REFUTE`, and `NO_EVIDENCE`; older
  `PARTIAL`/`WRONG_STATEMENT` values were retired.
- `MechanisticHypothesis`: disease-level metadata grouping alternative causal
  edges, including status, applicable subtypes, evidence, and notes.
- `Discussion`: `discussion_id`, prompt, kind, status, attachment pointers,
  rationale, proposed experiments, evidence, attribution, and lifecycle dates.
  A dedicated top-level `knowledge_gaps` slot is currently deferred;
  `kind: KNOWLEDGE_GAP` is the live representation.
- `Experiment`: a status-neutral structured design nested under a discussion
  when proposed. It already supports ontology-backed experiment type and model
  systems, perturbations, assays, readouts, controls, a decision criterion,
  entity references that results would support/refute, explicit supporting and
  refuting outcomes, protocol reference, datasets, and evidence. We reuse and
  extend this shape; we do not create a competing upstream experiment format.
- `ExperimentalModel` covers non-animal NAMs such as organoids, chips, cell
  lines, iPSC-derived systems, and primary culture. `AnimalModel` is separate.
  Both can link to mechanism nodes through `modeled_mechanisms`.
- `ModelMechanismLink` distinguishes what a model recapitulates, fails to
  recapitulate, perturbs, measures, or rescues. It separates link-level evidence
  from readout evidence and carries `fidelity` (`HIGH`, `MODERATE`, `LOW`, or
  `UNKNOWN`), limitations, biological model scale, and typed divergences.
  Fidelity is explicitly a coarse translational caveat, not a metric or proof of
  a human mechanism.

The causal pathograph is built primarily from `pathophysiology[].downstream`
and phenotype `sequelae`. Other sections join via explicit mechanism target
links. Node evidence and edge evidence are not interchangeable and the importer
preserves both.

DisMech also provides strong integrity machinery: LinkML validation, ontology
term validation, exact reference/snippet checks against cached source text,
rendering, and graph exports. Those capabilities should be reused upstream or
at the adapter boundary, not reimplemented as looser checks.

## Monarch already provides

The current public API is v3. Relevant endpoints include:

- entity metadata, search/autocomplete, mappings, and general association query;
- typed entity association tables;
- case-phenotype matrix/grid;
- disease-phenotype grid and ortholog-phenotype grid;
- generic traversable entity grids;
- HistoPheno and semantic-similarity endpoints;
- `/v3/api/pathograph/{node_id}` for a DisMech disease/gene pathograph.

`monarch-app` contains the website/API and `monarch-py` functionality. For V1,
the stable boundary is the documented HTTP API behind a small typed adapter.
Internal `monarch-py` storage implementations must not leak into domain models.

Monarch is association- and cross-species-rich. It is used for identity,
phenotype, gene, ortholog, and context expansion. It does not silently replace
DisMech causal statements. A Monarch association absent from DisMech becomes a
`CrossSourceDiscrepancy` review item; the converse is not automatically an
error because the two resources have different purposes.

## Documented limitations addressed here

Current DisMech documentation and open issues explicitly identify several
boundaries relevant to this product:

- evidence direction/directness is not a universal evidence-strength grade;
- the standard item does not fully capture experiment design, system,
  perturbation, comparator, replication, readout, result, or inferential role;
- a resolvable citation and verbatim snippet can still be attached to a claim it
  does not actually establish;
- background statements can be mistaken for results produced by the cited paper;
- human frequency assertions can be backed only by model-organism evidence;
- a paper cited elsewhere in an entry may contradict an asserted absence;
- pathophysiology evidence is not rendered in every module view;
- broad/umbrella disease entities can conceal mechanistic heterogeneity;
- structural knowledge gaps are discussions rather than a dedicated schema slot.

The refinement layer therefore adds paper-result provenance, study design and
experimental context, claim-evidence fit review, contradiction/context analysis,
search coverage, atomic claims, independently synthesized gap priority, and the
capability/collaborator action layer. Its experiment proposal is an internal
review object that can adapt an upstream DisMech `Experiment` when one exists or
produce a candidate for expert review when it does not. It does not invent a
scalar clinical or evidence score.

## Read-only and reuse policy

The following remain immutable source snapshots in V1:

- original DisMech document and its source path/URL;
- original node/edge text and evidence payloads;
- upstream identifiers, mappings, and hypothesis/discussion records;
- Monarch response snapshots used for a run.

Refined claims, evidence appraisals, narrowed wording, contradictions, gaps, and
experiments are new objects with `DERIVED_FROM` provenance. They never overwrite
an upstream claim.

## New internal objects

V1 needs `SourceSnapshot`, `Disease`, `Gene`, `Variant`, `Phenotype`,
`MechanismNode`, `MechanismEdge`, first-class `Claim`, extended `EvidenceItem`,
`EvidenceReview`, `Contradiction`, `CrossSourceDiscrepancy`, `SearchCoverage`,
`MechanisticHypothesis`, `KnowledgeGap`, `ExperimentProposal`, `Capability`,
`ResearchAsset`, `Person`, `Organization`, and `RefinementRun`.

## Candidate-demo selection

Demo choice must be data-driven. The importer includes a candidate summarizer
that ranks interpretable dimensions separately: pathophysiology/edge count,
citation count, gene and variant context, subtype/phenotype structure,
model-system coverage, and explicit gaps/controversies. Initial upstream leads
worth running through it include Sanfilippo syndrome type A, MBD5
haploinsufficiency, KBG syndrome, CHD2-related DEE, CMT2C, and CLOVES syndrome.
No disease is hard-coded as the winner.

## Primary upstream references

- DisMech repository and README: https://github.com/monarch-initiative/dismech
- Live LinkML schema: https://github.com/monarch-initiative/dismech/blob/main/src/dismech/schema/dismech.yaml
- Evidence model: https://github.com/monarch-initiative/dismech/blob/main/docs/explanation/evidence-model.md
- Design decisions: https://github.com/monarch-initiative/dismech/blob/main/docs/explanation/design-decisions.md
- Pathographs: https://github.com/monarch-initiative/dismech/blob/main/docs/pathographs.md
- Claim-fit failure issue #10609: https://github.com/monarch-initiative/dismech/issues/10609
- Evidence-strength boundary issue #9951: https://github.com/monarch-initiative/dismech/issues/9951
- Monarch application/API: https://github.com/monarch-initiative/monarch-app
- Monarch v3 OpenAPI: https://api.monarchinitiative.org/openapi.json
