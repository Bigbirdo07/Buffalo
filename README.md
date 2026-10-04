# Rare Disease Evidence Refininement & Action Engine

An auditable evidence-refinement layer over DisMech and the Monarch Knowledge
Graph. The project imports an upstream disease mechanism without modifying it,
creates atomic internal claims, records experiment-level evidence context, and
supports the path from a consequential uncertainty to a falsifiable research
proposal.

The first implemented vertical slice is deliberately backend-first:

- read-only DisMech YAML/JSON import with source snapshots and deterministic IDs;
- explicit Claim, EvidenceItem, mechanism, gap, experiment, provenance, and
  search-coverage models;
- edge-level evidence preservation (distinct from node evidence);
- graph construction and structural gap candidates;
- strict identifier and citation validation;
- a FastAPI application factory when the optional API dependencies are present;
- scientific fixture and unit tests.

This software summarizes research. It does not diagnose disease or recommend
medical treatment. Hypotheses and experiment proposals require qualified human
review.

## Quick start

Python 3.12+ is required.

```bash
python -m venv .venv
.venv/bin/pip install -e 'backend[dev]'
make test
make lint
make typecheck
```

Import a DisMech entry without changing it:

```bash
.venv/bin/python scripts/ingest_dismech.py path/to/DisMech_Disease.yaml \
  --source-version <dismech-commit> --output imported.json
```

Architecture and scientific boundaries are documented in [`docs/`](docs/).

## Hackathon UI

The seven-stage parent-first demo reads frozen contracts in `data/demo/` at
build time; it does not require the backend or external APIs during
presentation. It moves from a plain-language SCAR16 introduction through
research connections, evidence review, the open question, a falsifiable test,
existing research capacity, and a printable discussion summary.

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:4173/#/disease`. Run the complete frontend verification
with `npm run check` (contract/route tests, ESLint, TypeScript, and production
build).

## Status

Implemented: Phase 0 analysis, Phase 1 importer, Phase 2 core scientific models,
and Phase 3 real-data validation and first refinement cycle.

Phase 3 artifacts, all generated rather than described:

- all 3,289 real DisMech entries at commit `b923d18f` import with zero silently
  dropped fields — see [`docs/REAL_IMPORT_AUDIT.md`](docs/REAL_IMPORT_AUDIT.md);
- data-driven demo selection over visible dimensions, no composite score — see
  [`docs/DEMO_DISEASE_CANDIDATES.md`](docs/DEMO_DISEASE_CANDIDATES.md);
- one real mechanism edge refined end to end with hash-verified source
  snapshots, deterministic citation checks, independent per-pair review,
  categorical synthesis, a KnowledgeGap and a falsifiable ExperimentProposal —
  in [`data/refinement/scar16_stub1_e3/`](data/refinement/scar16_stub1_e3/).
- an acceptance matrix and pending scientific decisions — see
  [`docs/PHASE_3_ACCEPTANCE.md`](docs/PHASE_3_ACCEPTANCE.md) and
  [`docs/SCIENTIFIC_DECISIONS.md`](docs/SCIENTIFIC_DECISIONS.md);
- machine-readable claim lineage and an offline-verified reproducibility
  manifest in the refinement directory.

Reproduce the refinement offline from the cached snapshots:

```bash
PYTHONPATH=backend/src .venv/bin/python scripts/refine_edge.py \
  data/refinement/scar16_stub1_e3 --offline --output /tmp/edge_refinement.json

.venv/bin/python scripts/build_phase3_assurance.py
```

The evidence critic is a deterministic rule set, not an LLM and not human
review: no model API key is configured in this environment. Every scientific
conclusion carries `EXTRACTED` provenance and requires named expert review.

The hackathon UI is implemented in `frontend/` with family and scientist
presentation modes. It consumes `data/demo/flagship_story.json` and
`data/demo/goals_summary.json` as authoritative scientific contracts, plus the
source-linked `data/demo/parent_story.json` presentation contract, and performs
no scientific inference client-side. Production Postgres/Neo4j deployment and
live web enrichment remain separate from the offline demo.
