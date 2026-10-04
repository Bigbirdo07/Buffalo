# Phase 3 acceptance record

Source: DisMech commit
`b923d18f1c962eeaecf9f1f908305b21a8f26904`. This matrix maps each original
criterion to generated evidence. “Pass” means the software and artifacts meet
the machine-checkable requirement; it does not mean a scientific expert has
approved the interpretation.

| # | Acceptance criterion | Evidence | Verification | Status |
| --- | --- | --- | --- | --- |
| 1 | At least one real disease imports | 3,289 files in `data/audit/corpus_audit.json`; four real regression fixtures | `CorpusAuditSummaryTests`; `RealImportTests` | PASS |
| 2 | No upstream scientific information silently lost | Zero undeclared paths and zero unretained top-level items; preserved records retain payloads and hashes | `AuditAgainstRealDataTests`; `RealImportTests.test_no_silent_loss_in_any_real_fixture` | PASS |
| 3 | One real mechanistic edge independently refined | `edge_refinement.json`: 5 atomic claims, 16 observations, 21 independent reviews | `EdgeRefinementTests`; offline replay | PASS |
| 4 | Evidence context preserved | Species, cell type, variant, domain, subtype, system, intervention, assay and readout annotations | `EdgeRefinementTests.test_context_fields_required_by_the_protocol_are_present` | PASS |
| 5 | A real uncertainty/context limitation identified | Inter-domain/linker alleles retain bulk ligase activity in tested recombinant contexts | A6 atomic status and E2 edge synthesis | PASS |
| 6 | One valid KnowledgeGap produced | `knowledge_gap.json` | `KnowledgeGapTests` and strict Pydantic validation | PASS |
| 7 | One falsifiable ExperimentProposal produced | `experiment_proposal.json` | `ExperimentProposalTests` and strict Pydantic validation | PASS |
| 8 | Provenance remains traceable | Source commit/path/hash, observation-level evidence references and `claim_lineage.json` | `SnapshotIntegrityTests`; `Phase3AssuranceTests` | PASS |
| 9 | Tests, lint and type checks pass | `make check` | Unit/integration suite, Ruff and mypy | PASS; see final verification below |
| 10 | Upstream data and refinement are distinguished | Curated upstream claim stays `UNREVIEWED`; derived claims are `EXTRACTED`; critic/synthesis and human-review state are explicit | `EdgeRefinementTests.test_upstream_claim_is_unmodified_curated_content`; lineage artifact | PASS |

## Additional assurance controls

| Control | Evidence | Status |
| --- | --- | --- |
| Acceptance criteria map to artifacts and tests | This document | PASS |
| Scientific judgment calls are explicit | `docs/SCIENTIFIC_DECISIONS.md` | PASS; human review pending |
| Claim-to-experiment lineage is machine-readable | `data/refinement/scar16_stub1_e3/claim_lineage.json` | PASS |
| Pinned-source and cached replay are recorded | `data/refinement/scar16_stub1_e3/reproducibility_manifest.json` | PASS |
| Discovered failure modes have regression tests | Importer, critic, synthesis, artifact and assurance tests | PASS |

## Scientific result

The imported edge is `CONTEXT_DEPENDENT` under categorical rule E2. The result
does not use a numeric confidence score. The independent critic is deterministic
and rule-based; it is not an LLM and not human review.

The four interpretive decisions in `SCIENTIFIC_DECISIONS.md` remain `PENDING`
expert sign-off. This does not invalidate deterministic completion of Phase 3,
but it prohibits presenting the refinement or experiment as expert-approved.

## Final verification

Run from the workspace root:

```bash
.venv/bin/python scripts/build_phase3_assurance.py
make check
```

The assurance command fails closed if a cached body hash differs or if offline
reproduction differs after removing only execution timestamps. The exact
environment, per-file hashes, commands and replay result are recorded in the
reproducibility manifest. Final result: **149 tests passed; Ruff clean; mypy
clean across 39 checked source files.**
