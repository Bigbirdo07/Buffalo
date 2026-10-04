# Real DisMech import audit

Every number here is generated, not estimated. Regenerate with:

```bash
scripts/audit_corpus.py --disorders-dir data/upstream/dismech-checkout/kb/disorders \
  --commit b923d18f1c962eeaecf9f1f908305b21a8f26904 \
  --output data/audit/corpus_audit.json --metrics-output data/audit/candidate_metrics.json
```

- Upstream source: `monarch-initiative/dismech`, sparse read-only checkout at
  `data/upstream/dismech-checkout/`
- Pinned commit: `b923d18f1c962eeaecf9f1f908305b21a8f26904` (committed 2026-10-03)
- Audit date: 2026-10-03
- Machine-readable summary: [`data/audit/corpus_audit.json`](../data/audit/corpus_audit.json)

The earlier limitation is resolved: the importer was previously validated only
against a hand-written fixture because DNS could not reach GitHub. It is now
validated against the real upstream corpus, and the local
`data/upstream/dismech/Achondroplasia.yaml` placeholder that prompted that note
was an empty 0-byte file.

## Primary imported disease

| Field | Value |
| --- | --- |
| Disease name | Autosomal Recessive Spinocerebellar Ataxia 16 (SCAR16) |
| MONDO | `MONDO:0014339` |
| Source file | `kb/disorders/Autosomal_Recessive_Spinocerebellar_Ataxia_16.yaml` |
| Source commit | `b923d18f1c962eeaecf9f1f908305b21a8f26904` |
| Source bytes | 225,252 |
| Source SHA-256 | `034ccf003e36be04a5e3b87094cc704437c1577799267df60037664da2080942` |

| Imported object | Count |
| --- | --- |
| Mechanism nodes | 44 |
| Mechanism edges | 35 |
| Claims | 79 |
| Evidence items | 117 |
| Knowledge gaps (from `discussions`, `kind: KNOWLEDGE_GAP`) | 1 |
| Mechanistic hypotheses | 0 (this entry declares none) |
| Genes | 1 (STUB1, `HGNC:11427`) |
| Variants | 22 |
| Phenotypes | 23 |
| Experiment/model records preserved | 18 (`animal_models` + `experimental_models`) |
| Preserved upstream records (all sections) | 64 |
| **Silently dropped fields** | **0** |
| Warnings | 0 |

## Whole-corpus totals

All 3,289 disorder files were imported, not a sample.

| Metric | Value |
| --- | --- |
| Files seen | 3,289 |
| Files imported successfully | 3,289 |
| Files failed | 0 |
| **Undeclared field paths (silent loss)** | **0** |
| **Unretained top-level items (silent loss)** | **0** |
| Mechanism nodes | 65,559 |
| Mechanism edges | 46,555 |
| Claims | 111,618 |
| Evidence items | 117,842 |
| Imported knowledge gaps | 3,087 |
| Mechanistic hypotheses | 1,160 |
| Genes | 7,295 |
| Variants | 1,657 |
| Phenotypes | 42,116 |
| Preserved upstream records | 89,840 |

Nine files previously failed import on evidence entries with an empty `snippet`.
They now import, and the affected pointers are reported as
`EVIDENCE_WITHOUT_SNIPPET` warnings instead of aborting the file. An exact
supported span cannot be fabricated, so such a pointer is not turned into an
`EvidenceItem`; it stays verbatim in its parent's provenance payload.

## Normalized versus preserved: these are not the same thing

Preserving raw bytes is **not** normalization. A preserved field is auditable but
is not yet a typed scientific object, cannot be queried by meaning, and takes no
part in refinement. The distinction is tracked per field path.

| Disposition | Distinct field paths | Meaning |
| --- | --- | --- |
| `normalized` | 191 | Mapped into a typed internal field |
| `preserved_unnormalized` | 1,883 | Kept verbatim with provenance; **not** typed |
| `structural` | 14 | Containers (lists/objects) that hold other fields |
| `undeclared` | **0** | No declared handling — this is what silent loss would look like |

Full path lists are in `corpus_audit.json` under `normalized_field_paths` and
`preserved_field_paths`.

### Normalized (typed) upstream content

- identity: `name`, `description`, `synonyms`, `parents`, `category`,
  `disease_term.term.id` → `Disease.mondo_id`, `updated_date`/`creation_date`
- `pathophysiology[]`: `name`, `description`, `biological_scale`,
  `mechanism_confidence`, `role`, `subtypes`, and the 13 ontology descriptor
  slots (`genes`, `cell_types`, `biological_processes`, `locations`,
  `molecular_functions`, `cellular_components`, `chemical_entities`,
  `protein_complexes`, `pathways`, `gene_products`, `assays`, `triggers`, `gene`)
  → `MechanismNode.annotations[]`
- `pathophysiology[].downstream[]` and `phenotypes[].sequelae[]`: `target`,
  `description`, `causal_link_type`, `hypothesis_groups`,
  `intermediate_mechanisms` → `MechanismEdge` + `Claim`
- evidence (everywhere it appears): `reference`, `reference_title`, `snippet`,
  `supports`, `quote_role`, `evidence_source`, `explanation`, `directness`
- `phenotypes[]`: `name`, `description`, `phenotype_term.term.id` → `hpo_id`,
  `frequency`, `severity`, `context`, `subtype`/`subtypes`
- `genetic[].gene_term` → `Gene.symbol` + `Gene.hgnc_id`
- variants: `name`, `type`/`variant_type`, `clinical_significance`, `gene`
- `mechanistic_hypotheses[]`: id, label/description, `status`,
  `applies_to_subtypes`
- `discussions[]` with `kind: KNOWLEDGE_GAP`: `prompt`, `rationale`,
  `attaches_to`, `status`

### Preserved but not modeled

Every upstream scientific field not represented internally is listed here
explicitly. Each item becomes a `PreservedUpstreamRecord` carrying its source
object path, a payload SHA-256, and the source snapshot hash.

Whole sections, with corpus-wide record counts:

| Section | Records | Section | Records |
| --- | --- | --- | --- |
| `references` | 19,679 | `histopathology` | 1,034 |
| `treatments` | 13,949 | `categories` | 1,018 |
| `diagnosis` | 5,908 | `mappings` | 704 |
| `has_subtypes` | 4,571 | `epidemiology` | 410 |
| `differential_diagnoses` | 4,094 | `definitions` | 388 |
| `prevalence` | 3,014 | `external_assertions` | 365 |
| `progression` | 2,545 | `infectious_agent` | 322 |
| `inheritance` | 2,508 | `imaging_findings` | 308 |
| `animal_models` | 2,277 | `transmission` | 268 |
| `datasets` | 1,997 | `review_notes` | 244 |
| `notes` | 1,965 | `clinical_burden` | 203 |
| `clinical_trials` | 1,571 | `stages` | 116 |
| `classifications` | 1,506 | `computational_models` | 99 |
| `environmental` | 1,304 | `gene_sets` | 34 |
| `experimental_models` | 1,129 | `agent_life_cycle` | 23 |
| `biochemical` | 2,714 | `tracked_issues` | 21 |
| | | `modeling_considerations` | 13 |

Partially normalized sections, where identity is typed but scientific detail is
not (these are preserved **in addition to** being normalized):

- `genetic[]` (7,295 records): gene identity is typed; `association`,
  `relationship_type`, `variant_origin`, `inheritance[]`, `case_fractions[]`,
  `gene_disease_validity[]`, `features`, `frequency`, `presence`,
  `affected_regions[]` and all gene-level evidence are **not** typed.
- `variants` / `genetic[].variants[]` (290 top-level records): label, class and
  clinical significance are typed; `functional_effects[]`, `genomic_contexts`,
  `identifiers`, `external_assertions[]`, `regulatory_category`,
  `sequence_length` and variant-level evidence are **not** typed.
- `mechanistic_hypotheses[]` (1,160 records): statement and status are typed;
  hypothesis-level `evidence[]` and `notes` are **not** typed.
- `discussions[]` (4,794 records): only `kind: KNOWLEDGE_GAP` becomes a
  `KnowledgeGap`. The other 1,707 discussions (`HUMAN_MODEL_MISMATCH` 893,
  `OPEN_QUESTION` 268, `CONTROVERSY` 264, `INTERPRETATION` 182, `CURATION_TODO`
  51, `EMERGING_HYPOTHESIS` 41) and all `proposed_experiments[]`,
  `resolution_note`, `posed_by`/`posed_date` and discussion evidence are **not**
  typed. 2,188 upstream `proposed_experiments` are preserved and unmodeled —
  the largest single body of unmodeled scientific structure.

Known consequence: upstream `ExperimentalModel`/`AnimalModel`
`modeled_mechanisms` links (1,852 + 1,048 occurrences) are preserved but not yet
joined to mechanism nodes, so model-to-mechanism traversal is not available
internally even though the data is retained.

## Warnings

Corpus-wide, from `warnings_by_code`:

| Code | Count | Meaning |
| --- | --- | --- |
| `DANGLING_EDGE_TARGET` | 496 | A `downstream.target` string matches no node name. An `UNSPECIFIED` referenced node is created so the edge is never dropped. |
| `PHENOTYPE_LABEL_SHADOWED` | 165 | A phenotype name duplicates an earlier node label; edges targeting that label resolve to the earlier node. |
| `NON_HPO_PHENOTYPE_TERM` | 28 | `phenotype_term` resolves to a non-HPO CURIE; `hpo_id` is left empty rather than coerced. |
| `EVIDENCE_WITHOUT_SNIPPET` | 27 | Evidence pointer with no quotable span; not normalized into an `EvidenceItem`. |
| `MONDO_FROM_MAPPINGS` | 18 | `disease_term` carried no MONDO id, so one was taken from `mappings.mondo_mappings`. |

SCAR16 itself produced zero warnings.

## Parser ambiguities

1. **`phenotypes[].frequency` is not a controlled vocabulary.** 102 distinct
   values mix Orphanet classes (`FREQUENT`, `VERY_FREQUENT`, `OCCASIONAL`,
   `OBLIGATE`), prose (`Frequent (79-30%)`), and bare HPO frequency term ids
   (`HP_0040282`). Stored as free text; not parsed into a scale.
2. **`pathophysiology[].role` is open.** 138 distinct values. Stored verbatim in
   `upstream_role`; no enum imposed.
3. **`category` is open.** 63 distinct values, so `Disease.disease_type` is free
   text.
4. **Duplicate node labels.** Phenotype and pathophysiology names can collide;
   an edge target string cannot then distinguish them (see
   `PHENOTYPE_LABEL_SHADOWED`).
5. **`genetic[].variants[].gene` may disagree with the parent `gene_term`.** The
   variant's own `gene` wins; the parent symbol is the fallback.
6. **Reference prefixes are heterogeneous.** 16 schemes across the corpus
   (`PMID` 204,054; `ORPHA` 7,408; `DOI` 5,677; bare `url` 5,349;
   `clinicaltrials`, `CGGV`, `GEO`, `PPR`, `ICTRP`, `NCIT`, `CIVIC_*`, `CGDS`,
   `STRCHIVE`). Only `PMID`/`PMCID`/`DOI` map to typed identifier fields; the
   rest land in `other_reference`, and only PMIDs are deterministically
   verifiable today.

## Normalization decisions

1. **CURIE prefixes are upper-cased** for a known set (`hgnc:3690` →
   `HGNC:3690`; also MONDO, HP, GO, CL, UBERON, CHEBI, NCBITaxon). Upstream
   writes gene prefixes in lower case. Unknown prefixes are left untouched.
2. **Ontology ids are read from the nested `term.id`**, which is where the live
   schema puts them. The earlier flat `{id, label}` assumption silently lost
   every MONDO, HGNC and HPO identifier in the real corpus.
3. **`biological_scale` drives `MechanismNodeCategory`**
   (`MOLECULAR`/`CELLULAR`/`TISSUE`/`ORGANISM`); absent scale falls back to
   pathway/complex presence, else `UNSPECIFIED`.
4. **`supports` maps to relation**: `SUPPORT`→supports, `REFUTE`→refutes,
   `NO_EVIDENCE`→neutral. The retired `PARTIAL` value is still accepted
   (→qualifies) for older entries; unrecognized values warn and become neutral.
5. **`quote_role` maps to origin and section**: `PRIMARY_RESULT`→primary result,
   `BACKGROUND`→cited background + introduction,
   `REVIEW_SYNTHESIS`→review synthesis + review summary. Absent `quote_role`
   (204,521 of 226,106 evidence items) becomes `database_assertion` with
   `UNKNOWN` section — it is not assumed to be a primary result.
6. **Node and edge evidence stay separate.** Edge evidence is never inherited
   from its source node.
7. **`functional_effect` is never inferred.** Upstream `functional_effects` text
   is preserved; our enum stays `unknown` pending review.
8. **Species is not assumed for evidence.** Only `HUMAN_CLINICAL` evidence gets
   `Homo sapiens`; everything else is left empty.
9. **Phenotype `sequelae` are imported as causal edges**, alongside
   `pathophysiology.downstream`, since both are upstream causal assertions.
10. **Source locators are cwd-independent.** The locator is the path from
    `kb/disorders/` onward, so deterministic UUIDv5 ids do not change with the
    working directory. This was a real defect: importing the same file by
    relative versus absolute path previously produced different claim ids and
    broke provenance reconstruction.
11. **Upstream curator text is kept but kept separate.** `explanation` →
    `curator_explanation`, `directness` → `upstream_directness`. These are
    upstream opinion, not our appraisal, and the critic does not consume them.

## Audit method and its limits

`audit_fields()` walks every path in the document, normalizes list indices, and
resolves each path against a declared rule table. A path with no rule is
reported as `UNDECLARED`; a top-level item not present in any imported object's
provenance is reported as `unretained`. Both are asserted to be zero in
`backend/tests/test_field_audit.py`, which also injects fields that do not exist
upstream and asserts they *are* flagged — so the zero is a measurement, not an
assumption.

What this audit does **not** claim:

- It does not verify that a normalized value is scientifically correct, only that
  it is represented and traceable.
- It does not check upstream snippets against cited sources (that is citation
  validation, run per refinement).
- A field being preserved does not make it usable; see the normalized/preserved
  split above.
