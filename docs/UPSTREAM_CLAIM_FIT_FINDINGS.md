# Claim-fit findings across the DisMech corpus

Every entry here is a **risk flag for curator review, not a proven error.** Each
detector states the question it asks and the way it can be wrong, because a flag
list whose precision is unstated invites either blind trust or blanket dismissal.

Nothing in this audit needs manual extraction, an LLM or a network call: it reads
fields the importer already parses, so it runs over the whole corpus.

```bash
PYTHONPATH=backend/src .venv/bin/python scripts/audit_claim_fit.py \
  --commit b923d18f1c962eeaecf9f1f908305b21a8f26904
```

- Source: `monarch-initiative/dismech` at `b923d18f`
- Files examined: **3,289**, zero parse failures
- Findings: **4,906** across **660 diseases** (20% of the corpus)
- Machine-readable: [`data/audit/claim_fit.json`](../data/audit/claim_fit.json)
- 4,145 of 4,906 findings sit on mechanism objects (pathophysiology nodes and
  edges, mechanistic hypotheses, phenotype sequelae)

| Detector | Severity | Findings | Asks |
| --- | --- | --- | --- |
| `UNVERIFIABLE_SOLE_SUPPORT` | medium | 2,036 | Is every supporting citation in a form no checker can resolve? |
| `REVIEW_ONLY_SUPPORT` | medium | 1,542 | Is every supporting citation a review rather than a primary result? |
| `BACKGROUND_ONLY_SUPPORT` | **high** | 991 | Is every supporting citation marked background rather than the paper's own result? |
| `DUAL_FORM_CITATION` | low | 185 | Is one publication cited in two identifier forms, so it will not deduplicate? |
| `DIRECT_EDGE_NO_EVIDENCE` | medium | 114 | Does a DIRECT causal edge have no evidence anywhere, including its endpoints? |
| `HUMAN_FREQUENCY_MODEL_ONLY` | **high** | 24 | Does a human-population frequency rest only on model-organism evidence? |
| `CONFIDENCE_CONTRADICTS_EVIDENCE` | **high** | 14 | Is a mechanism marked ESTABLISHED while carrying its own refuting citations? |

## The three highest-value lists

These are short enough to work through by hand and specific enough to act on.

### Human frequency resting only on model-organism evidence — 24 findings

A frequency stated as `VERY_FREQUENT` or `FREQUENT` is a claim about people. Where
every attached citation is `evidence_source: MODEL_ORGANISM`, the stated evidence
cannot support the stated frequency. This is a limitation DisMech's own
documentation names.

| Disease | Phenotype | Frequency | Sole support |
| --- | --- | --- | --- |
| Congenital Stationary Night Blindness | Night Blindness | VERY_FREQUENT | PMID:37220680 |
| Bietti Crystalline Dystrophy | Chorioretinal Atrophy | VERY_FREQUENT | PMID:38992691 |
| Dilated Cardiomyopathy 1HH | Dilated Cardiomyopathy | — | PMID:21353195 |
| CMT Recessive Intermediate | Gait Difficulty | FREQUENT | PMID:25152455 |

*How this can be wrong:* the frequency may come from a source the curator did not
attach. The flag means the stated evidence cannot support the stated frequency,
not that the frequency is wrong.

### ESTABLISHED confidence alongside refuting evidence — 14 findings

A mechanism labelled `ESTABLISHED` that carries its own `REFUTE` or `NO_EVIDENCE`
citations. Either the label is too strong or the refuting citation bears on a
narrower sub-claim that should be separated out.

| Disease | Mechanism node | Contrary citation |
| --- | --- | --- |
| Adult-Onset Proximal SMA (AD) | ER-Derived Aggregation of Misfolded VAPB | PMID:24252306 |
| Combined OXPHOS Deficiency | Lactate and Pyruvate Accumulation | PMID:39544688 |
| Combined OXPHOS Defect | Lactate Accumulation | PMID:27759031 |
| Constitutional Mismatch Repair Deficiency | Impaired Ig Class-Switch Recombination | PMID:30013564 |

*How this can be wrong:* a refuting citation legitimately attached to a narrower
sub-claim is a reasonable curation pattern. The flag asks whether the confidence
label still fits.

### DIRECT causal edges with no evidence anywhere — 114 findings

An edge asserting the strongest causal link type, with no evidence of its own
**and** no supporting evidence on either endpoint node.

| Disease | Transition |
| --- | --- |
| Alpha-1 Antitrypsin Deficiency | Alveolar Tissue Destruction → Emphysema |
| Amatoxin Poisoning | Hepatic Synthetic and Metabolic Failure → Acute liver failure |
| 46,XY Sex Reversal 5 | Loss of Negative Feedback → Elevated circulating FSH |
| 46,XY Sex Reversal 5 | Loss of Negative Feedback → Elevated circulating LH |

This detector is worth reading as a precision story. Flagging every DIRECT edge
without edge-level evidence returned **9,913** hits — 53% of all DIRECT edges,
which makes it a curation convention rather than an anomaly: evidence commonly
sits on the nodes. Requiring that neither endpoint carries evidence either cuts
it to **114**, a 98.8% reduction. Those 114 are the genuinely unsupported
transitions, and several are arguably textbook steps a curator would call
self-evident.

## Background-only support — 991 findings

The largest high-severity list, and the failure mode DisMech tracks as issue
**#10609**: a resolvable citation with a verbatim snippet attached to a claim it
does not establish. Here, every supporting citation is marked
`quote_role: BACKGROUND`, so the quoted sentence is attributed to earlier work
rather than to the cited paper's own findings.

383 of these sit on pathophysiology nodes and edges. Example:
`16p11.2_Deletion_Syndrome` → `pathophysiology[0].downstream[0]`
("Reduced 16p11.2 Gene Dosage"), whose only support is PMID:28984295 marked
background.

This project found the same pattern by hand during the SCAR16 refinement: a 2026
paper's introduction states that STUB1 p.Lys145Gln impairs CHIP ligase activity,
citing a 2018 study whose own data report that allele as *not overtly different
from wild type*. That case is not in this list, because the citation was attached
to a different node than the one it undermines — which is a limit of the
detector worth stating.

Two deliberate design choices keep this list honest:

- **An absent `quote_role` is not treated as background.** The field is unset on
  204,521 of 226,106 evidence items, so inferring background from silence would
  have produced a list of mostly noise.
- **Refuting citations do not count as support**, so a node whose only
  *supporting* citation is background is flagged even if it carries primary
  refuting evidence.

## Identifier hygiene — 185 findings

One evidence list mixing PMID-form and PMC-form references. Where a pair denotes
the same publication it will not deduplicate, and independence counting can treat
one study as two. That matters directly: this engine's own rule for contradicting
a claim requires **two independent publications**.

A confirmed instance: `Autosomal_Recessive_Spinocerebellar_Ataxia_20`,
`pathophysiology[1]` cites both `PMID:29635513` and
`url:https://pmc.ncbi.nlm.nih.gov/articles/PMC5961352/` — the NCBI ID converter
resolves the latter to the former.

This count was derived independently before the detector existed and matched at
185, which is the one precision figure here that has a cross-check. A test pins
it.

*How this can be wrong:* detected offline, so co-occurrence is reported without
confirming the two forms denote one publication. A preprint and its journal
version would legitimately be separate records.

## Auditability, not correctness — 2,036 findings

Mechanism claims whose every supporting citation uses a reference form with no
resolver. Scoped to mechanism objects, because ORPHA and registry references are
ordinary for prevalence and clinical entries.

Corpus-wide at the item level: **15,653 of 226,106 evidence items (6.9%)** cannot
be verified by any automated check — ORPHA 7,408, non-PMC URLs 4,627,
clinicaltrials 1,819, CGGV 1,391. Adding PMC and DOI resolvers moved
checkability from 90.2% to **93.1%**; an ORPHA resolver is the largest remaining
single gain.

## What this audit does not do

- **It does not read papers.** Every detector reasons about curation metadata —
  polarity, quote role, evidence source, reference form, confidence label — never
  about whether a claim is biologically true.
- **It does not rank diseases by quality.** The most-flagged entries
  (Baraitser-Winter Cerebrofrontofacial Syndrome, 117; Acute Tricyclic
  Antidepressant Poisoning, 97; Aortic Valve Stenosis, 86) are mostly the
  *largest and most thoroughly curated*. Flag count tracks curation volume, so
  reading it as a quality score would penalise the best-documented entries.
- **It has no measured precision.** Only `DUAL_FORM_CITATION` has an independent
  cross-check. For the others, the false-positive modes above are reasoned, not
  measured. Establishing precision needs a curator to adjudicate a sample, which
  is the obvious next step and has not been done.
- **It is not a defect list and should not be sent as one.** The useful form is a
  question per finding: does this citation establish this claim?
