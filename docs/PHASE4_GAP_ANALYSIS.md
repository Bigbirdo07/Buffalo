# Phase 4 gap analysis

## Scope and boundary

Phase 3 is a stable scientific input to Phase 4. The action engine must consume
the accepted `KnowledgeGap` and `ExperimentProposal`; it must not rewrite the
DisMech source claim, atomic claims, evidence reviews, synthesis status, or
immutable literature snapshots. Human decisions are append-only review records,
not mutations of machine output.

## Present and reusable

- `ExperimentProposal` already provides the scientific question, competing
  hypotheses, model and sample contexts, controls, endpoints, limitations,
  required-asset phrases, and required-capability phrases.
- The SCAR16/STUB1 proposal is a complete Phase 4 seed. It explicitly requests
  endogenous STUB1 editing, neuronal differentiation, diGly ubiquitin
  proteomics, protein assays, and clone-aware statistical analysis.
- `KnowledgeGap`, `SearchCoverage`, `Provenance`, `SourceSnapshot`, and
  `ModelInvocation` provide reusable audit primitives.
- Phase 3 content-addressed snapshots, deterministic identifiers, evidence
  references, claim lineage, and reproducibility manifest remain authoritative.
- The current `Capability`, `ResearchAsset`, `Person`, and `Organization`
  classes are preliminary placeholders. Their data have not been used in the
  Phase 3 scientific synthesis, so they can be expanded without migrating the
  scientific artifacts.

## Missing product capabilities

1. There is no append-only `ScientificReview` overlay or accepted-value record.
2. Experiment requirements are strings rather than typed `RequiredCapability`
   and `RequiredAsset` records with derivation evidence.
3. There are no source-specific discovery records, web claims, capability
   claims, entity-resolution decisions, labs, grants, studies, programs, or
   collaboration opportunities.
4. Search coverage cannot yet record pagination, language, geography, cache
   behavior, or retrieval cost.
5. PubMed currently supports mechanism evidence retrieval, not team-level
   capability discovery. NIH RePORTER and ClinicalTrials.gov action adapters do
   not exist.
6. Bright Data is not integrated. It must enter only after requirement-driven
   query generation, producing unverified `WebEvidenceCandidate` records. It
   must not directly produce a verified capability.
7. There is no canonical database repository, schema migration mechanism, or
   Neo4j projection.
8. The API exposes only `/health`; there is no complete patient/scientist
   journey.

## New domain models

- Review: `ScientificReview`, review target/status enums, and an append-only
  review history capable of representing disagreement.
- Requirements: `RequiredCapability`, `RequiredAsset`, categories, necessity,
  derivation evidence, and review status.
- Discovery: `Researcher`, `Laboratory`, `Organization`, `ResearchAsset`,
  `Grant`, `ClinicalStudy`, `ResearchProgram`, and explicit provenance.
- Evidence: `WebEvidenceCandidate`, `WebClaim`, `CapabilityClaim`, source
  quality/directness, recency, corroboration, verification state, and content
  hashes.
- Resolution: explicit entity-resolution decisions including
  `POSSIBLE_DUPLICATE`; ambiguous records must remain separate.
- Action: dimensioned candidate matches and `CollaborationOpportunity` with
  supplied and missing requirements, uncertainties, potential duplication,
  roles, review state, and next action.
- Operations: action-search coverage, Bright Data usage, cache/freshness
  metadata, and source failures.

## External integrations

Implementation order is PubMed/PMC, NIH RePORTER, ClinicalTrials.gov, patient
organization sources, repository APIs, then targeted institutional web
discovery. Official structured APIs are used instead of scraping. ORCID may
assist identity resolution but is never sufficient alone.

Bright Data is reserved for high-value unstructured institutional, laboratory,
foundation, registry, and repository pages. It records query, endpoint, pages,
estimated usage, cache status, raw snapshot hash, relevant passages, and
retrieval time. Extracted web claims begin as unverified and require
corroboration or human review.

## Migration and persistence implications

Postgres becomes the canonical operational and audit store. Initial migrations
must import existing JSON artifacts without changing their bytes or IDs and
store their content hashes and locations. Reviews are new rows linked to target
versions. Accepted interpretations are derived views over immutable machine
objects plus review history.

The first persistence slice should use SQLAlchemy models and repositories that
work with Postgres in production and SQLite in isolated tests. Tables require
JSON payloads for lossless round trips plus indexed identity, status, version,
and timestamp columns. A migration/version table is required before production
data is written. Neo4j remains a rebuildable projection and cannot contain
canonical-only state.

## What remains unchanged

- Phase 3 scientific schemas and categorical synthesis rules.
- All source snapshots and their SHA-256 values.
- Existing claim/evidence/knowledge-gap/experiment identifiers.
- The distinction between upstream assertions and Atlas refinements.
- The rule that proposals require expert review and are not clinical advice.

## Delivery sequence

1. Append-only human scientific review.
2. Deterministic structured capability and asset extraction from the existing
   experiment.
3. Requirement-driven query generation and structured-source adapters.
4. Bright Data candidate discovery, caching, accounting, and web-claim
   verification.
5. Entity resolution, dimensioned matching, duplication qualification, and
   collaboration synthesis.
6. Postgres persistence with lossless import and lineage queries.
7. Rebuildable Neo4j projection.
8. Minimal patient and scientist views of the same traced journey.

## Acceptance map

Phase 4 acceptance requires one SCAR16 chain from the existing experiment to
typed requirements, searched sources, evidence-qualified candidate people/labs
and assets, a reviewable collaboration proposal, explicit missing requirements,
patient and scientist explanations, database round-trip, and complete lineage.
Source failures, language/geography limits, stale records, and absence findings
must be displayed rather than converted into negative claims. Tests must cover
false personal capability transfer, historical activity, active grants, weak
web claims, potential duplication, context-mismatched assets, and empty search
results. The phase is not complete until tests, Ruff, and mypy pass and no
unsupported collaborator claim is represented as established fact.
