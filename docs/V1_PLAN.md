# V1 implementation plan

## Completed

- Phase 0: upstream/source/API analysis and architectural/scientific protocols.
- Phase 1: read-only DisMech import boundary, deterministic identities, source
  snapshots, pathophysiology/phenotype graph mapping, node-versus-edge evidence,
  hypotheses/discussion gap import, and candidate-demo metrics.
- Phase 2: typed Claim, extended EvidenceItem, EvidenceReview, hypothesis, gap,
  experiment, provenance, and search-coverage models with deterministic
  validation.
- Deterministic graph reachability and structural gap candidates.
- Unit/scientific fixture tests for wrong-disease, background-only, mouse-human,
  cell-context, variant-domain, and mixed evidence cases.
- Phase 3: real-corpus validation (3,289 entries, zero silent field loss),
  regression fixtures derived from four real entries, snapshot-cached
  PubMed/Europe PMC/UniProt retrieval, deterministic citation and quotation
  checking, a rule-based independent evidence critic, categorical synthesis
  (rules A1-A7, E1-E5), and one complete edge refinement producing a
  KnowledgeGap and an ExperimentProposal.
- Phase 3 assurance: machine-readable claim lineage, cached offline replay,
  per-file and artifact hashes, an acceptance matrix, a scientific decision
  register, and adversarial regression coverage for discovered failure modes.
  Human scientific review remains pending.

## Next increments in priority order

1. Persist snapshots/runs in Postgres with Alembic; add a rebuildable Neo4j
   projection and reconciliation test.
2. Join the preserved `modeled_mechanisms` links to mechanism nodes so
   model-to-mechanism traversal works internally.
3. Build the mechanism API and restrained Cytoscape scientist view.
4. Add model-assisted atomic decomposition behind the existing replayable,
   schema-validated interface; retain the deterministic baseline.
5. Query NIH RePORTER, ClinicalTrials.gov, repositories, and verified web
    sources for capabilities/assets/collaborators.
6. Add patient-leader narrative and scientist evidence tables.
7. Benchmark, temporal evaluation, demo polish, and reproducible release.

## Definition of done for the demo

The 20 acceptance criteria in the master specification are tracked as evidence,
not as UI claims. A criterion closes only with a fixture/run artifact and test or
human-review record. No treatment recommendation or clinical decision support is
in scope.

## Explicit limitations

The initial slice does not claim expert evidence adjudication, collaborator
discovery, production persistence, or a completed UI. The critic is a
deterministic rule set, not an LLM or human reviewer. Network failures must
remain visible in coverage. Candidate analysis was run over the pinned upstream
checkout; SCAR16 is the first-cycle selection, not a hard-coded final disease.
