# Goal 1 audit — who genuinely shares this disease's biology?

Run from a disease, not a chosen pair. `Autosomal Recessive Spinocerebellar Ataxia 16` went in; the neighbours
below came out of retrieval and were then evaluated independently.

- 60 candidates retrieved · top 8 evaluated · commit `97d46adf5018`
- Machine-readable: [`data/goals/goal1_scar16_neighbors.json`](../data/goals/goal1_scar16_neighbors.json)

## The whole point: retrieval and validation are different answers

| # | Candidate | Found because | Independent? | Evidence says | Was the reason right? |
| --- | --- | --- | --- | --- | --- |
| 1 | Spinocerebellar Ataxia 48 | protein quality control  | no | `SHARED_DOWNSTREAM_MECHANISM` | `CORRECT` |
| 2 | Cerebellar Ataxia-Hypogonadism Syn | ubiquitin-dependent prot | no | `SHARED_DOWNSTREAM_MECHANISM` | `INCORRECT_BUT_CONNECTION_REAL` |
| 3 | Autosomal Dominant Cerebellar Atax | protein quality control  | no | `INSUFFICIENT_EVIDENCE` | `UNRESOLVED` |
| 4 | Peroxisome Biogenesis Disorder 5B | Purkinje cell | no | `SHARED_CELLULAR_PROCESS_NON_EQUIVALENT` | `INCOMPLETE` |
| 5 | Neurodevelopmental Disorder With o | protein ubiquitination | yes | `SHARED_DOWNSTREAM_MECHANISM` | `INCORRECT_BUT_CONNECTION_REAL` |
| 6 | Lafora Disease | protein ubiquitination | yes | `SHARED_DOWNSTREAM_MECHANISM` | `INCORRECT_BUT_CONNECTION_REAL` |
| 7 | Friedreich Ataxia | mitophagy | no | `SHARED_TISSUE_CONTEXT` | `INCOMPLETE` |
| 8 | Fragile X-Associated Tremor Ataxia | ubiquitin-dependent prot | no | `INSUFFICIENT_EVIDENCE` | `UNRESOLVED` |

Read the last two columns together. They disagree for most candidates, and that
disagreement is the product.

## Which are independent diseases, and which are not?

**6 of 8 are not independent discoveries.**

Ranks 1 and 2 — Spinocerebellar Ataxia 48 and Cerebellar Ataxia-Hypogonadism
Syndrome — are the system's two strongest retrieval hits, and both are excluded.
They share the anchor's causal gene, and identity checking classifies them as
`PARTIALLY_OVERLAPPING_ENTITY` with a gene-scoped `ALLELIC_SPECTRUM` verdict
beneath. A system that reported its top two hits as cross-disease discoveries
would be reporting the same disease under other names.

This is checked *before* any mechanism claim, because the alternative is
inflating every downstream count.

## Which were rejected, and why

- **Fragile X-Associated Tremor Ataxia Syndrome** — `INSUFFICIENT_EVIDENCE`.
  Retrieved 15 co-mentioning papers, of which one survived scrutiny. The rest
  matched a laboratory method whose acronym differs from the anchor protein's
  only by case. See the defect section below.
- **Friedreich Ataxia** — `SHARED_TISSUE_CONTEXT`. Comparable tissue, no
  demonstrated molecular relationship.
- **Autosomal Dominant Cerebellar Ataxia Type I** — `INSUFFICIENT_EVIDENCE`.
  One primary finding, below the corroboration bar.

## Which is only a shared process?

**Peroxisome Biogenesis Disorder 5B** — `SHARED_CELLULAR_PROCESS_NON_EQUIVALENT`.
Retrieved on a shared molecular-function annotation, but nothing demonstrates the
diseases disrupt it equivalently. An independent literature review of this pair
reached the same conclusion for a stronger reason: the underlying chemistry runs
in opposite directions.

## The strongest independent neighbour

Two survive as independent corroborated relationships: **Lafora Disease** and
**Neurodevelopmental Disorder With or Without Autism or Seizures**.

The automated criterion ranks by corroboration count and prefers the
neurodevelopmental pair (4 findings to 2). **Lafora was kept as the worked
flagship by operator override, and the automated ranking is preserved in the
artifact rather than overwritten.** The reason is that Lafora's relationship has
been independently checked against primary literature and the other has not —
and corroboration count measures how many papers co-mention two diseases, not
how well the mechanism is understood. That is a limitation of the ranking rule,
and it is a question for expert review rather than something the system should
settle.

### Why Lafora is defensible

Retrieved through a broad `protein ubiquitination` annotation. That annotation is
**not** why the pair is real: the two ligases act on different substrate classes.
Independent evidence retrieval found papers showing one protein physically
stabilises the other, and both sit in a shared stress-response complex — giving
`SHARED_DOWNSTREAM_MECHANISM` with `INCORRECT_BUT_CONNECTION_REAL`.

**The system found a real neighbour and then corrected its own explanation for
why.** That is the operation a similarity score cannot perform.

## A defect this audit exposed

Running eight candidates instead of four hand-picked ones immediately produced a
wrong answer: **six of eight were reported as sharing a downstream mechanism.**

Two causes, both fixed generally:

1. **An acronym collision the pipeline failed to inherit.** The anchor protein's
   acronym differs from a ubiquitous laboratory method's only by case, and the
   method co-occurs with essentially every gene. Confirmation is now
   case-sensitive, which PubMed search cannot be.
2. **A mechanism claim with no nameable mechanism.** One pair reached
   `SHARED_DOWNSTREAM_MECHANISM` while no mechanistic bridge could be derived
   from its evidence. A shared mechanism that cannot be named is now reported as
   `INSUFFICIENT_EVIDENCE`.

After the fix: 5 relationships, 3 rejected, and the distribution above.

Finding this required running the system on candidates nobody had chosen. That
is what this audit is for.

