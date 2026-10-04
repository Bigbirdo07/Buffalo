# Blind cross-disease evaluation — round 2

Four candidate pairs run through the decision pipeline with the round-1 review
verdicts sealed, then compared.

**Blindness is enforced, not promised.** The runner installs a
`sys.addaudithook` that aborts the process if anything opens
`data/validation/cross_disease_round1.json`. The pipeline module itself has no
filesystem or network access: it classifies the inputs it is handed. Evidence is
retrieved per pair by co-mention search built from each disease's own entities,
so what a pair gets depends on the pair, never on a verdict.

- Pipeline: `cross-disease-pipeline-v1`
- Machine-readable: [`data/validation/cross_disease_round2.json`](../data/validation/cross_disease_round2.json)
- Traces: `data/cross_disease/traces/*.json`
- **2 agree, 2 partial, 0 disagree**

## Results

| Pair | Retrieval reason | Pipeline identity | Pipeline relationship | Reviewed | Retrieval validity | Agreement | Right reason? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SCAR16 × Lafora | SHARED_CELLULAR_PROCESS (protein ubiquitination) | DISTINCT_DISEASE | SHARED_DOWNSTREAM_MECHANISM | SHARED_MECHANISM_SUPPORTED | INCORRECT_BUT_CONNECTION_REAL | **AGREE** | **Yes** |
| SCAR16 × Rabies | SHARED_CELLULAR_PROCESS (mitophagy) | DISTINCT_DISEASE | SHARED_TISSUE_CONTEXT | confirmed false positive | INCOMPLETE | **AGREE** | **Yes** |
| SCAR16 × Peroxisome BD 5B | SHARED_MOLECULAR_FUNCTION | DISTINCT_DISEASE | INSUFFICIENT_EVIDENCE | SHARED_PROCESS_ONLY_SUPERFICIAL | UNRESOLVED | PARTIAL | No |
| SCAR16 × Gordon Holmes | SAME_GENE (STUB1) | PARTIALLY_OVERLAPPING_ENTITY | SHARED_DOWNSTREAM_MECHANISM | same allelic entity | INCORRECT_BUT_CONNECTION_REAL | PARTIAL | Partly |

## The flagship case worked

For **SCAR16 × Lafora** the pipeline independently retrieved **PMID:19892702**
and **PMID:21652633** — the two papers the reviewer named as the strongest
evidence for a CHIP–malin link — and classified the pair as
`SHARED_DOWNSTREAM_MECHANISM` with retrieval validity
`INCORRECT_BUT_CONNECTION_REAL`.

That second field is the point. The pair was retrieved on a shared "protein
ubiquitination" annotation, and that annotation is *not* why the pair is real:
malin ubiquitinates glycogen enzymes while CHIP triages chaperone clients. The
system now records both facts at once — the connection is genuine, the stated
reason for finding it was wrong. That is the exact state the architecture was
rebuilt to represent, and it arrived from a blind run.

## Where it is weaker than the reviewer

**It reaches negative verdicts by absence rather than by argument.** For the
peroxisome pair the reviewer could show the chemistry is near-opposite —
reversible Cys-thioester monoubiquitination for receptor recycling versus K48
polyubiquitination for destruction. The pipeline only found too little evidence
to assert anything, and said `INSUFFICIENT_EVIDENCE`. The actionable outcome
matches (neither asserts a shared mechanism) but the reasoning does not.

**Three of four pairs cite no literature in common with the reviewer.** Agreement
on a label is not agreement on a reading of the field, which is why this audit
scores the biological reason separately.

**Evidence retrieval is title-and-abstract only**, so a relationship discussed
solely in full text is invisible.

## Four general fixes, each from a measured failure

None are disease-specific; the no-special-case guard remained active throughout.

1. **Protein aliases.** The first blind run returned *zero* hits for Lafora. The
   query was built from HGNC symbols while the literature says CHIP and malin. A
   UniProt adapter now resolves gene symbols to protein names. A zero-hit search
   is indistinguishable from "no relationship exists", which makes this the most
   dangerous failure mode in the system.
2. **Retrieval terms versus confirming terms.** Adding the bare acronym fixed
   recall and destroyed precision: "CHIP" matched ChIP (chromatin
   immunoprecipitation) papers and every pair became a shared mechanism,
   including Rabies. Broad aliases may now *retrieve* a paper; only unambiguous
   terms may *confirm* one. This is the project's retrieval-versus-evidence
   separation applied one level down.
3. **Disambiguation by context.** An ambiguous acronym counts only when the
   other disease is named unambiguously in the same publication. A paper
   established to be about malin that also says "CHIP" is using the protein
   sense; the same token elsewhere is noise.
4. **Corroboration.** One pair rested on a single paper and was reported as a
   shared mechanism. Asserting a mechanism now requires two independent primary
   findings — the same bar this system already applies before accepting that a
   claim is contradicted.

## Identity checking changed one answer

Gordon Holmes initially came back `DISTINCT_DISEASE`. A general rule was added:
where one disease's entire causal gene set is contained in another's, the
narrower label is likely a genetic subtype of a broader, genetically
heterogeneous entity. It now returns `PARTIALLY_OVERLAPPING_ENTITY` and requests
expert sign-off.

The reviewer goes further and treats the two as one allelic spectrum. The
pipeline is more conservative because upstream lists four causal genes for the
broader entity against one for the narrow one — a defensible difference, and one
for a curator to settle rather than for the pipeline to assume.
