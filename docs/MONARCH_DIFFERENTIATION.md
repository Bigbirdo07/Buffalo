# What this adds to an integrated biomedical knowledge graph

Written against one worked result, not in the abstract.

**Monarch is not a competitor and is not wrong here.** Monarch excels at
integrated biomedical associations, ontology relationships and semantic
discovery across species, and this project consumes its data: every disease
entry comes from DisMech, a Monarch Initiative project, and the mechanism
representations this system reasons over are DisMech's work. Nothing below
suggests otherwise.

The question is narrow: given an association graph that already returns
diseases, genes, phenotypes and their connections, what additional operation
does this system perform?

## The same pair, two layers

**Association layer** (what a knowledge graph returns):

> `Autosomal Recessive Spinocerebellar Ataxia 16` and `Lafora Disease` are connected because
> both are annotated with **protein ubiquitination**.

That is true, useful, and where a graph query stops.

**This system's layer:**

| Question | Answer for this pair |
| --- | --- |
| Why was it retrieved? | `SHARED_CELLULAR_PROCESS, SHARED_CELL_TYPE, PHENOTYPE_SIMILARITY` on *protein ubiquitination* |
| Are these independent diseases? | `DISTINCT_DISEASE` — two of the top hits were not, and were excluded |
| Is the retrieval reason the real reason? | **`INCORRECT_BUT_CONNECTION_REAL`** |
| What does the evidence say instead? | ['chaperone', 'co-chaperone', 'ubiquitin ligase', 'CHIP', 'stress response', 'HSF1'] |
| From what? | PMID:21652633, PMID:19892702, read as primary findings |
| How deeply was it read? | `ABSTRACT_OR_DERIVED_SOURCE` — full text not obtained |
| What remains unknown? | whether the diseases converge *functionally* at that node |
| What would settle it? | one experiment with an explicit refutation condition |
| What already exists to run it? | 4 of 5 capabilities have a published candidate; 1 unknown; no verified collaborator |

## The operation that is genuinely different

The pair was retrieved on a broad process annotation. **That annotation is not
why the pair is real** — the two ligases act on different substrate classes. The
system went to the literature independently, found a different and more specific
basis, and recorded both facts at once:

```
found by      protein ubiquitination        (annotation — wrong explanation)
supported by  chaperone, co-chaperone, ubiquitin ligase, CHIP   (evidence)
```

An association graph has no place to put that distinction, because it has no
notion of an explanation being wrong while the connection is right. This system
has a controlled value for it, and that value appears on 3 of the
8 candidates evaluated.

## What the layering buys, concretely

Of the top 8 retrieved neighbours:

- **2** were excluded as the same allelic spectrum under different names — they
  were ranks **1 and 2**, the strongest retrieval hits
- **3** were rejected or downgraded on evidence
- **1** was shared-process-only
- **2** survived as independent corroborated relationships

A ranked association list would have returned the same eight and offered no
basis for separating them. The separation is the product.

## What this system does not do

It does not integrate across species, maintain ontologies, resolve entities at
scale, or serve a public API. It consumes those capabilities rather than
providing them. It is a layer that stress-tests a small number of connections
and converts the survivors into a research decision — not a replacement for the
graph that found them.

## The honest summary

> An association graph tells you two diseases are connected, and why its data
> say so. This system asks whether that reason survives the evidence, what the
> real connection is if the reason does not, what remains unknown about it, what
> experiment would resolve that, and what already exists to run it.
>
> On this pair the retrieval reason did not survive, the connection did, and the
> system said so.

