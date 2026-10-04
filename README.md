# Rare Disease Atlas

**An auditable evidence-refinement layer over DisMech.**

Built for Hack-Nation's 7th Global AI Hackathon, Challenge 05 — *AI Atlas for the
World's Rare Diseases*.

The atlas takes a rare disease and answers three questions with its evidence
attached: **who genuinely shares its biology**, **what useful work already
exists**, and **what important thing nobody knows yet**. It is designed to be
wrong out loud — most of what it retrieves does not survive its own review, and
the interface shows you what it threw away.

```
Follow the biology.  Check the evidence.  Find the next research question.
```

---

## Table of contents

- [The problem this solves](#the-problem-this-solves)
- [Quick start](#quick-start)
- [What the product does](#what-the-product-does)
- [The five worked cases](#the-five-worked-cases)
- [Scientific architecture](#scientific-architecture-the-part-that-matters)
- [The flagship case, in full](#the-flagship-case-in-full)
- [How anything here is verified](#how-anything-here-is-verified)
- [What we found in the upstream corpus](#what-we-found-in-the-upstream-corpus)
- [Corpus and system numbers](#corpus-and-system-numbers)
- [Repository layout](#repository-layout)
- [Reproducing everything](#reproducing-everything)
- [What this does *not* claim](#what-this-does-not-claim)
- [Document index](#document-index)

---

## The problem this solves

[DisMech](https://github.com/monarch-initiative/dismech) (Monarch Initiative) is
a curated corpus of disease mechanisms — 3,289 disorders, one LinkML YAML file
each, with citations attached to claims. It is genuinely good data, and this
project does not modify a byte of it.

But a curated association graph has a structural blind spot. When it links two
diseases, it records **that** they share a feature. It has nowhere to record the
distinction a scientist makes instantly:

> *"The reason this connection surfaced is wrong — but the connection is real."*

That sentence is the most common honest verdict on a literature-derived link, and
there is no field for it. So a graph either asserts the connection (overclaiming)
or drops it (losing a real lead).

This project adds the missing layer. It separates **why something was retrieved**
from **what the evidence supports**, keeps both, and refuses to collapse them.

### Why not just query Monarch?

| | Monarch / DisMech | This project |
|---|---|---|
| Unit of record | curated association | atomic claim + the evidence that supports it |
| Retrieval reason | implicit in the edge | a **first-class object** with no evidence field |
| Can express "found for the wrong reason" | no | `INCORRECT_BUT_CONNECTION_REAL` |
| Same disease, two names | both appear as neighbours | identity resolved **before** any mechanism claim |
| Output | a subgraph | a falsifiable experiment with a refutation clause |
| Null results | absent | first-class, with a reason |

See [`docs/MONARCH_DIFFERENTIATION.md`](docs/MONARCH_DIFFERENTIATION.md).

---

## Quick start

Requires Python 3.11+ and Node 20+. No Docker, no API keys, no network.

```bash
# Backend: 441 tests, ruff, mypy, and an offline rebuild of every artifact
make verify

# Frontend: the product
cd frontend && npm install && npm run dev
# → http://127.0.0.1:5173/
```

Then search **SCAR16** and press *Follow the biology*.

Everything in the demo runs from frozen local data. There are **no live API calls
during the presentation**, by design.

---

## What the product does

The interface is a **traced biological lineage**, not a dashboard. One disease
enters at the bottom; the biology grows upward one step at a time.

```
                            ?  ← the path ends at what nobody knows
                            │
                    Lafora Disease
                            │
              Cellular stress response
                            │
                          CHIP          (protein)
                            │
                         STUB1          (gene)
                            │
                        SCAR16          ← you started here
```

**Progressive disclosure is the mechanism, not a flourish.** SCAR16 opens as a
single node. Everything in this subject connects to everything, so a complete
graph on arrival teaches nobody anything. A test asserts the protein and the
related disease are *absent* from the DOM until requested.

Each node draws its label, its entity type, and a plain-language meaning. Shapes
differ by type — disease circle, gene hexagon, protein diamond, process rounded
rectangle — so the kind of thing is readable before the words are. Nothing
essential hides behind a hover.

### Three views, one dataset

| Route | What it is |
|---|---|
| `#/search` | Search across all 3,289 diseases |
| `#/trace?case=scar16` | The lineage walkthrough (arrow keys advance it) |
| `#/atlas?case=scar16` | The same findings as three goal panels, for a technical reader |

Search covers the whole corpus. Any disease returns its **real candidate
neighbours** computed locally in ~6 ms — and then an explicit panel stating that
deep evidence refinement has been run for five diseases and this is not one of
them. That panel is as much the point as the results are: it is where the app
visibly refuses to overstate.

---

## The five worked cases

Three produced a complete chain. **Two produced nothing** — and the nulls carry
more weight than the hits, because they show the system refuses when the evidence
is not there.

| Case | Outcome | What it demonstrates |
|---|---|---|
| **SCAR16** (STUB1) | `FULL_CHAIN` | The flagship. A real connection found for the wrong reason. |
| **Lafora Disease** | `FULL_CHAIN` | Reverse anchor — starting from the neighbour recovers the STUB1 family independently. |
| **Ankylosing Spondylitis** | `FULL_CHAIN` | Not an ataxia tool. Immune disease; **5 of 8 leads rejected**. |
| **Zellweger Spectrum** | `NO_DEFENSIBLE_CONNECTION` | Every candidate was *the same disease entity* under another name. |
| **SCAR20** | `NO_DEFENSIBLE_CONNECTION` | Candidates were distinct diseases, but **no evidence supported any of them**. |

Those last two are different *kinds* of null, and the contract distinguishes
them: `ALL_CANDIDATES_ARE_THE_SAME_ENTITY` vs `NO_SUPPORTING_EVIDENCE`.

### There is no disease-specific code

A test (`test_allowlist_is_empty`) asserts the special-case allowlist is
**empty**. The code path that produced SCAR16 × Lafora is the code path that runs
on anything in the corpus. The limit on coverage is compute and literature
access, not architecture.

---

## Scientific architecture (the part that matters)

### Three levels of claim, which the type system refuses to merge

```python
RetrievalReason          # why we looked. Has NO evidence_ids field at all.
ValidatedRelationship    # what evidence supports. Raises without evidence_ids.
MechanisticBridge        # the functional step, read from evidence text. Versioned.
```

This is enforced structurally, not by convention:

- `RetrievalReason` **cannot** hold evidence. The field does not exist, so no
  future contributor can accidentally promote a hunch into a finding.
- `ValidatedRelationship` **raises in `model_post_init`** if it asserts a
  mechanistic class without evidence IDs.
- A `KnowledgeGap` **cannot be built** without a bridge. The function raises.

All models are Pydantic v2, frozen, `extra="forbid"`. IDs are deterministic
UUIDv5, so the same input always produces the same identifier and artifacts
diff cleanly.

### The verdict that makes this project necessary

```
RetrievalValidity.INCORRECT_BUT_CONNECTION_REAL
```

The relationship is real. The annotation that surfaced it is the wrong
explanation. **Both facts are retained, and the UI draws both** — the original
broad edge stays on the canvas, dimmed, while the refined bridge grows beside it.
A test asserts that superseded edge is still in the DOM after refinement.

### Identity before mechanism

Two names for one disease must never become a "shared mechanism" finding. Every
candidate is resolved for identity *first*:

`SAME_ALLELIC_SPECTRUM` · `PHENOTYPIC_SUBTYPE` · `PARTIALLY_OVERLAPPING_ENTITY` ·
`DISTINCT_DISEASE`

Identity can also be **scoped**, which is how a genuinely hard case is handled
rather than flattened. Broad Gordon Holmes syndrome is a
`PARTIALLY_OVERLAPPING_ENTITY`; the *STUB1-associated* Gordon Holmes phenotype is
`SAME_ALLELIC_SPECTRUM`. One disease label, two correct answers at two scopes.

### Falsifiability is enforced in code

`assert_falsifiable()` raises on any proposal with:

- no refuting outcome,
- outcomes that cannot be distinguished by the primary readout, or
- an empty primary readout.

An experiment that could only confirm cannot be returned. The UI gives the
refuting branch equal visual weight — neither outcome is styled as a win.

### No LLM anywhere in the reasoning path

There are **zero** model calls in `services/` or `domain/`. Every verdict is
deterministic code over curated data and literature search. Same input, same
output, re-runnable offline. You can audit why it reached any conclusion.

---

## The flagship case, in full

**SCAR16 × Lafora Disease.**

1. **Retrieval** surfaced the pair through a broad shared annotation
   (protein ubiquitination). Retrieval is the hypothesis-generating step and it
   is wrong about *why* a pair matters more often than it is right.
2. **Identity resolution** confirmed these are distinct diseases — not two labels
   for one entity.
3. **Evidence review** found the broad annotation was not the operative link, but
   that two independent primary findings supported a more specific one:
   **CHIP–malin interaction in stress-response / proteostasis biology**.
4. **Verdict:** `INCORRECT_BUT_CONNECTION_REAL`.
5. **The gap:** do both diseases produce the *same type* of cellular
   stress-response failure? The bridge establishes the proteins interact. It does
   **not** establish functional equivalence.
6. **The experiment:** both disease models through the same stress challenge,
   same primary readout, shared healthy control. Similar response strengthens a
   shared downstream mechanism; divergent response weakens it and says the
   diseases should be studied separately.
7. **Capability map:** 5 atomic capabilities derived from the frozen experiment
   and searched independently. **4 have supported candidates; 1 is unknown.**
   Topology `MULTI_PARTY_EXECUTABLE` — no single group holds every piece.

**Status: `AWAITING_EXPERT_SIGNOFF`.** No scientist has reviewed this. The review
packet is at [`docs/EXPERT_REVIEW_PACKET.md`](docs/EXPERT_REVIEW_PACKET.md).

---

## How anything here is verified

Four layers ran. **None of them is a human expert.**

### 1 · Citation level (automated, everything)

Does the PMID resolve? Does the quoted span appear in the retrieved text? Is it
the paper's own result or background? PMC and DOI forms resolve to one identifier
so a single paper cannot be double-counted as corroboration.

### 2 · Rule level (automated, everything)

- A mechanism claim requires **two independent primary findings**.
- Identity is resolved **before** any mechanism claim.
- Co-mention searches returning **> 2,000 hits** are rejected as
  `TOO_BROAD_TO_ESTABLISH_LINK`.
- Acronym matching is **case-sensitive** — CHIP the protein is not ChIP the assay.
- Hub genes are suppressed; retrieval and anchoring use *different* specificity
  thresholds (5% and 1%) because one shared threshold produced a giant component.

### 3 · Blind evaluation (four SCAR16 pairs)

Verdicts were sealed and blindness **enforced at runtime** by a
`sys.addaudithook` that aborts the process if the sealed file is opened.

**Result: 2 agree, 2 partial, 0 disagree.**

On SCAR16 × Lafora the pipeline independently retrieved **PMID:19892702** and
**PMID:21652633** — the same two papers an independent review named as
strongest.

### 4 · Independent literature review

A separate research pass checked each pair against primary literature with PMIDs.

**The honest caveat:** three of four pairs cite *no literature in common* with
that review. Agreement on a label is not agreement on a reading of the field.
Full detail in [`docs/CROSS_DISEASE_ROUND2_AUDIT.md`](docs/CROSS_DISEASE_ROUND2_AUDIT.md).

---

## What we found in the upstream corpus

A claim-fit audit ran every detector over all 3,289 files — **4,906 findings, zero
parse failures**. These are *fit-between-claim-and-citation* observations, not
assertions that the upstream science is wrong, and each detector ships with its
own documented false-positive mode.

| Detector | Findings | Question asked |
|---|---|---|
| `UNVERIFIABLE_SOLE_SUPPORT` | 2,036 | Is every citation in a form no automated check can resolve? |
| `REVIEW_ONLY_SUPPORT` | 1,542 | Is every citation a review rather than a primary result? |
| `BACKGROUND_ONLY_SUPPORT` | 991 | Is every citation marked background rather than the paper's own result? |
| `DUAL_FORM_CITATION` | 185 | Is one publication cited twice in two identifier forms, so it does not deduplicate? |
| `DIRECT_EDGE_NO_EVIDENCE` | 114 | Does a DIRECT causal edge carry no evidence, on itself or either endpoint? |
| `HUMAN_FREQUENCY_MODEL_ONLY` | 24 | Does a human-population frequency rest only on model-organism evidence? |
| `CONFIDENCE_CONTRADICTS_EVIDENCE` | 14 | Is a mechanism marked ESTABLISHED while carrying its own REFUTE citations? |

`DUAL_FORM_CITATION` matters most for this project's own correctness: if one paper
counts twice, the two-independent-findings rule is defeated. That is why
reference identity resolution runs before corroboration counting.

Full writeup: [`docs/UPSTREAM_CLAIM_FIT_FINDINGS.md`](docs/UPSTREAM_CLAIM_FIT_FINDINGS.md).

---

## Corpus and system numbers

Pinned to DisMech commit `b923d18f1c96`.

| | |
|---|---|
| Disorder files seen / imported | **3,289 / 3,289** |
| Parse failures | **0** |
| Undeclared field paths | **0** |
| Unretained top-level items | **0** |
| Claims | 111,618 |
| Evidence items | 117,842 |
| Nodes | 65,559 |
| Edges | 46,555 |
| Phenotypes | 42,116 |
| Genes | 7,295 |
| Variants | 1,657 |
| Hypotheses | 1,160 |
| Imported gaps | 3,087 |
| Preserved records | 89,840 |
| Backend tests | **441** (+14 subtests) |
| Frontend tests | **45** |

The importer loses nothing: zero undeclared paths and zero unretained top-level
items means every field in every upstream file is either mapped or explicitly
preserved. Audit: [`docs/REAL_IMPORT_AUDIT.md`](docs/REAL_IMPORT_AUDIT.md).

---

## Repository layout

```
backend/src/atlas/
  domain/          Pydantic models — the scientific contract
    cross_disease.py   RetrievalReason / ValidatedRelationship / MechanisticBridge
    fingerprint.py     DiseaseMechanismFingerprint, measured feature availability
  services/        All reasoning. No LLM calls.
    candidate_generation.py   IC-weighted retrieval, hub suppression
    hpo_similarity.py         Resnik similarity, corpus-derived information content
    disease_identity.py       identity resolution, scoped identities
    disease_comparison.py     pairwise comparison, molecular anchoring
    mechanism_clustering.py   Louvain communities over shared mechanism
    cross_disease_pipeline.py classification + bridge derivation
    cross_disease_synthesis.py gaps, experiments, assert_falsifiable()
    flagship_selection.py     weighted, auditable case selection
  adapters/        Read-only external sources
    europepmc/     text-mined annotations, role classification
    uniprot/       protein aliases and acronym extraction

scripts/           24 reproducible pipeline stages
frontend/src/
  lineage.tsx      the traced lineage canvas (the product)
  goals.tsx        the same findings as three goal panels
  search.tsx       corpus search + honest depth-limit panel
  contract.ts      zod schemas — the UI validates its own data contract
data/
  demo/            frozen UI contracts (cases, browse index, goal summary)
  validation/      blind evaluation records
  audit/           corpus and claim-fit audits
docs/              26 documents — audits, decisions, assumptions, review packets
```

The frontend **validates every contract with zod at load time** and renders a
`ContractUnavailable` screen rather than a half-broken page if validation fails.

---

## Reproducing everything

```bash
make verify          # 441 tests, ruff, mypy, and a full offline artifact rebuild
```

`make verify` aggregates by **exit code**, not by grepping output for "passed" —
an earlier version of this repo committed through a ruff failure twice because an
output filter matched the wrong string.

Regenerating a case from scratch, with no disease-specific flags:

```bash
scripts/run_cross_disease_pairs.py  --anchor "Ankylosing Spondylitis" --top 8 --out data/cross_disease_as
scripts/build_flagship_journey.py   --relationships data/cross_disease_as/relationships.jsonl --out data/flagship_as
scripts/refine_flagship_bridge.py   --journey data/flagship_as/flagship_journey.json --out data/flagship_as/bridge_refinement.json
scripts/build_flagship_goal2.py     --journey data/flagship_as/flagship_journey.json --out data/flagship_as/goal2_map.json
```

Source snapshots are SHA-256 content-addressed; IDs are deterministic UUIDv5.
The same inputs always produce the same artifacts.

---

## What this does *not* claim

Stated plainly, because a tool that hides its limits is worse than one that has
them.

**No expert has reviewed any of this.** Every scientific conclusion is
`AWAITING_EXPERT_SIGNOFF`. The review packet exists; no answer has come back.

**Full text was never obtained for the two key flagship papers.** One is
non-open-access; the other has no PMC record. The central mechanistic bridge is
read from abstract-level annotations, and `evidence_depth` records this. A
specialist with journal access may reach a different bridge.

**Evidence retrieval is co-mention search over titles and abstracts.** A
relationship discussed only in a full-text methods section is invisible to it.

**Negative verdicts are reached by absence of evidence**, not by the positive
contrary reasoning a reviewer would give. Same actionable outcome, weaker
reasoning — recorded rather than smoothed over.

**Capability means a team published this once.** Current availability is
unverified and **willingness to collaborate is never inferred**. The status is
literally `NO_VERIFIED_COLLABORATOR_IDENTIFIED`.

**No world map.** Every researcher record has `country: null`, and affiliations
name a place only as the paper printed it. Plotting pins would mean inferring
where people are *now* from where a paper was written years ago. The capability
strip ships without a map and says why.

**Retrieval covers 3,289 diseases; deep refinement covers five.** That is a
compute and access limit, not an architectural one — but it is a real limit and
the UI states it on every non-analysed disease.

### Not medical advice

This is a **research-support prototype**. It does not diagnose disease,
recommend treatment, or tell anyone what to do medically. Every screen carries
that notice. Discuss medical decisions with a qualified healthcare professional.

---

## Document index

**Start here**
- [`docs/SCIENTIFIC_MODEL.md`](docs/SCIENTIFIC_MODEL.md) — the data model and why it is shaped this way
- [`docs/MONARCH_DIFFERENTIATION.md`](docs/MONARCH_DIFFERENTIATION.md) — what this adds over the upstream graph
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system structure

**The science**
- [`docs/SCIENTIFIC_DECISIONS.md`](docs/SCIENTIFIC_DECISIONS.md) — every judgement call, with its reasoning
- [`docs/SCIENTIFIC_ASSUMPTIONS.md`](docs/SCIENTIFIC_ASSUMPTIONS.md) — what is assumed and where it could fail
- [`docs/EVIDENCE_REFINEMENT.md`](docs/EVIDENCE_REFINEMENT.md) — how a claim is refined

**Audits**
- [`docs/REAL_IMPORT_AUDIT.md`](docs/REAL_IMPORT_AUDIT.md) — proof the importer loses nothing
- [`docs/UPSTREAM_CLAIM_FIT_FINDINGS.md`](docs/UPSTREAM_CLAIM_FIT_FINDINGS.md) — 4,906 claim-fit findings
- [`docs/CROSS_DISEASE_ROUND2_AUDIT.md`](docs/CROSS_DISEASE_ROUND2_AUDIT.md) — the blind evaluation
- [`docs/GOALS_AUDIT_FINAL.md`](docs/GOALS_AUDIT_FINAL.md) — all three goals proven on real data
- [`docs/GOAL1_AUDIT.md`](docs/GOAL1_AUDIT.md) · [`GOAL2_AUDIT.md`](docs/GOAL2_AUDIT.md) · [`GOAL3_AUDIT.md`](docs/GOAL3_AUDIT.md)
- [`docs/GENERALIZATION_TEST_SCAR20.md`](docs/GENERALIZATION_TEST_SCAR20.md) — the null result

**The flagship**
- [`docs/FLAGSHIP_JOURNEY.md`](docs/FLAGSHIP_JOURNEY.md) — source to experiment
- [`docs/FLAGSHIP_GOAL2_REPORT.md`](docs/FLAGSHIP_GOAL2_REPORT.md) — the capability map
- [`docs/EXPERT_REVIEW_PACKET.md`](docs/EXPERT_REVIEW_PACKET.md) — what we would hand a specialist
- [`docs/FLAGSHIP_FOR_PATIENT_GROUPS.md`](docs/FLAGSHIP_FOR_PATIENT_GROUPS.md) — the same case in plain language

---

## Acknowledgements

Built on [DisMech](https://github.com/monarch-initiative/dismech) and the
[Monarch Initiative](https://monarchinitiative.org/), used read-only and
unmodified. Phenotype semantics from the
[Human Phenotype Ontology](https://hpo.jax.org/). Literature annotations from
[Europe PMC](https://europepmc.org/); protein aliases from
[UniProt](https://www.uniprot.org/).

Challenge 05 is supported by OpenAI and the Buffalo Initiative.
