# Scientific model

## Four epistemic layers

The model never collapses these categories:

- **Observation**: a measured or reported result in a defined system.
- **Established knowledge**: a scoped synthesis justified by reviewed evidence.
- **Hypothesis**: a falsifiable explanation with alternatives and assumptions.
- **Action**: an expert-reviewed experiment or collaboration proposal.

Likewise, provenance is explicit: `CURATED`, `EXTRACTED`, `INFERRED`, or
`HYPOTHESIS`. A display must show text labels in addition to color.

## Claims and edges

A mechanism edge references one atomic claim. “Gene loss impairs mitochondria
and causes neurodegeneration” must become multiple claims because each
transition can have different evidence and context. Imported broad statements
remain preserved as source claims while decomposed claims derive from them.

An edge status is one of `SUPPORTED`, `PARTIALLY_SUPPORTED`,
`CONTEXT_DEPENDENT`, `INSUFFICIENT_EVIDENCE`, or `CONTRADICTED`. Status is not a
universal numeric evidence score.

## Evidence

Evidence stores objective study facts: bibliographic identity, exact supported
span and section, whether it is a primary result/background/review assertion,
relation to the claim, modality/design, sample and replicate counts, species,
tissue, cell, subtype, variant/domain, intervention/comparator/readout,
statistics, limitations, extraction confidence, and human-review state.

Study design and sample size remain inspectable dimensions. They are not folded
into an opaque score. A source can support a narrower claim while qualifying or
refuting a broader one.

## Contradiction

Apparent disagreement is evaluated for species, tissue, cell type, age/stage,
assay, dose, mutation class, protein domain, subtype, and model-system
differences. An explainable scope difference is `CONTEXT_DEPENDENT`; a genuine
incompatible result can be `CONTRADICTED`. Both evidence sets remain visible.

## Knowledge gaps

A gap is a consequential unresolved relationship, not merely low publication
count. Priority dimensions are separately named: causal centrality, downstream
dependence, conflict, translational relevance, tractability, asset availability,
and ability to discriminate alternatives. A UI may summarize priority only
while displaying these reasons.

Every gap carries `SearchCoverage`: sources, query text, timestamps, status,
result counts, and failures. Wording is “no direct evidence identified in the
searched sources,” never a proof of absence.

## Experiments

An experiment is a research proposal requiring expert review. It specifies the
question, focal and competing hypotheses, model/sample and stratification,
perturbation/comparator/controls/readouts/endpoints, support and refutation
conditions, confounders, limitations, capabilities/assets, ethics flags, and
what it cannot justify.

DisMech already has a structured, status-neutral `Experiment` object with model
systems, perturbations, readouts, controls, decision criteria, and paired
support/refutation outcomes. The internal proposal maps those fields and adds
workflow-specific sample stratification, endpoints, confounders, capability and
asset requirements, ethics flags, and explicit unjustified interpretations.
Imported upstream proposals remain curated source records; generated proposals
are separate hypothesis-level records.

## Variants and models

Functional effect is unknown unless evidence supports a value. Variant class,
position/domain, molecular consequence, inheritance, and phenotype context are
preserved. Exploratory clusters are “candidate mechanistic subgroups,” never new
clinical subtypes without validation.

Model-organism results are cross-species support, not proof of human disease
mechanism. Orthology type, allele/model, tissues, recapitulated phenotypes,
fidelity, divergences, and species limitations scope every model inference.
