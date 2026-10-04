# Evidence refinement protocol

## Passes

### A. Immutable import

Snapshot the upstream file, hash it, record commit/version and retrieval date,
and map nodes, edges, hypotheses, discussions, and evidence. Preserve unknown
upstream fields in source payloads for forward compatibility.

### B. Atomic extraction

Use deterministic splitting only for explicit upstream edges. Semantic
decomposition uses a low-variance structured model call. Every output cites the
source claim ID and exact original statement. Schema-invalid output is rejected.

### C. Retrieval

Start with cited references, then search disease/gene/variant/protein/pathway/
phenotype/tissue/cell/model combinations. Prefer primary results; reviews orient
and lead to primary citations. Store every query and failure in coverage.

### D. Claim-evidence fit

Test disease/gene/direction/species/tissue/cell/variant match, whether the paper
tested the claim, whether the passage is its own result, direct versus indirect
support, and the strongest wording licensed by the result.

### E. Adversarial retrieval

Generate negative and competing-mechanism queries and seek replication in other
systems. Context mismatch is analyzed before labeling contradiction.

### F. Context resolution

Resolve species, tissue, cell, subtype, variant class/domain, disease stage/age,
model, intervention, assay, comparator, and readout. Unknown is a valid value.

### G. Independent critic

The critic receives only the atomic claim, source passage/metadata, and
experimental context—not extractor rationale or confidence. It returns a strict
`EvidenceReview` object and proposed scope narrowing.

### H. Synthesis

Synthesis sees all evidence and critic outputs and returns a categorical status
plus written rationale citing evidence IDs. It explicitly separates observation,
knowledge, and hypothesis.

## Deterministic gates

Before scientific synthesis, validate structured output, citation identifiers,
ontology CURIE syntax, source disease and gene, exact retained quotations,
required evidence IDs, and enum values. A failed lookup is `UNVERIFIED`, not
silently accepted. Automated text repair must never erase contradictions.

## Human review

High-consequence edge acceptance, final gap selection, experiment release, and
collaboration recommendations require named human review. Model output is stored
with inputs and versions so a run can be reconstructed without conversation
history.

