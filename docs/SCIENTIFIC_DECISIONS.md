# Phase 3 scientific decision register

These decisions constrain interpretation of the SCAR16/STUB1 refinement. They
are not upstream DisMech assertions and are not expert-approved conclusions.
Each remains `PENDING` human scientific review.

## SD-01 — K145Q and M211I structural classification

- **Decision:** Represent p.Lys145Gln and p.Met211Ile as
  `inter-domain/linker-region` variants. Do not normalize them as coiled-coil
  variants.
- **Reason:** The cached UniProt Q9UNE7 feature record does not place either
  residue in an annotated coiled-coil feature. Some papers group these alleles
  under a CC label; that wording remains source-specific context, not an
  authoritative domain assignment.
- **Alternatives rejected:** `coiled-coil variants` as normalized fact; a single
  undifferentiated STUB1 missense class.
- **Evidence:** `c325be09-0223-5168-a17b-8874c643986f#o08`,
  `c215671b-911e-548a-93d7-c2338562826a#o04`, plus the cached UniProt Q9UNE7
  snapshot cited by the observations' derived domain annotations.
- **Status effect:** No change. `ac4-interdomain-missense` remains
  `INSUFFICIENT_EVIDENCE` under A6. This decision prevents an unsupported
  structural label from narrowing the claim.
- **Basis:** Interpretive normalization decision.
- **Human review:** `PENDING`.

## SD-02 — N65S functional effect

- **Decision:** Code p.Asn65Ser as a `processivity_defect`, not as established
  `substrate_selective` activity.
- **Reason:** The direct experiments show impaired HSC70 polyubiquitin-chain
  elongation/mono-ubiquitination with retained CHIP self-ubiquitination. They do
  not compare multiple substrates, so substrate selectivity is not demonstrated.
- **Alternatives rejected:** total loss of E3 activity; established
  substrate-selective activity.
- **Evidence:** `c325be09-0223-5168-a17b-8874c643986f#o07` and
  `7fe75fee-a6f0-5b1f-b0dc-0e3cb3411424#o09`; the unchanged bulk result is
  `c325be09-0223-5168-a17b-8874c643986f#o08`.
- **Status effect:** No change. A processivity defect is direct qualification,
  so `ac3-tpr-missense` remains `CONTEXT_DEPENDENT` under A5.
- **Basis:** Data-derived readout interpretation with conservative terminology.
- **Human review:** `PENDING`.

## SD-03 — Self- versus substrate ubiquitination

- **Decision:** Keep `self_ubiquitination`, `hsc70_ubiquitination`,
  `hsp70_polyubiquitination`, and `polyubiquitin_chain_formation` as distinct
  readouts. Self-ubiquitination is not a substitute for substrate
  ubiquitination when judging the selected edge.
- **Reason:** These assays interrogate related but non-equivalent functions. A
  variant can retain self-ubiquitination while failing to extend chains on
  HSC70. Collapsing the readouts would conceal the observed heterogeneity.
- **Evidence:** `c325be09-0223-5168-a17b-8874c643986f#o07` and
  `7fe75fee-a6f0-5b1f-b0dc-0e3cb3411424#o09` explicitly contrast the readouts.
- **Status effect:** Self-ubiquitination is excluded from the selected claim's
  admissible readout family. It can qualify biological interpretation but
  cannot independently support or refute substrate ubiquitination loss.
- **Basis:** Assay-semantics decision.
- **Human review:** `PENDING`.

## SD-04 — SCA48 as cross-entity evidence

- **Decision:** Keep dominant SCA48 separate from recessive SCAR16. SCA48
  biochemical findings can be `QUALIFIES/INDIRECT` for a SCAR16 claim, never
  direct causal evidence for that claim solely because both involve STUB1.
- **Reason:** A proposed disease continuum does not erase differences in
  allelic state, inheritance, phenotype, or experimental context.
- **Alternatives rejected:** pooling SCA48 and SCAR16 as one disease context;
  excluding SCA48 evidence entirely.
- **Evidence:** `retrieved:PMID:42567515#o14`,
  `retrieved:PMID:42567515#o15`, and `retrieved:PMID:35398354#o16`.
- **Status effect:** These observations remain indirect and cannot set the
  SCAR16 atomic-claim status. They qualify the mechanistic interpretation.
- **Basis:** Disease-scope interpretation.
- **Human review:** `PENDING`.

## Review requirement

Approval must record reviewer identity, date, decision ID, and whether the
decision was accepted, amended, or rejected. Until then, the generated
KnowledgeGap and ExperimentProposal remain research outputs requiring expert
review.
