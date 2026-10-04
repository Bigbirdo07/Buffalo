# Goal 2 — what exists, who has shown it, what is missing

Three distinct questions, deliberately not collapsed into "find collaborators":
who has a capability we need, what already exists that could be reused, and
whether another group may already be doing overlapping work.

- Commit `a100b591ac45` · [`data/action/flagship_goal2_map.json`](../data/action/flagship_goal2_map.json)
- **4 of 5 capabilities have a candidate** · topology `MULTI_PARTY_EXECUTABLE`
- `NO_VERIFIED_COLLABORATOR_IDENTIFIED` · assets: `NO_RELEVANT_ASSET_IDENTIFIED`

## What the experiment needs

> Do Autosomal Recessive Spinocerebellar Ataxia 16 and Lafora Disease converge on a shared functional defect in chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) in disease-relevant models, measured by at least one identical primary functional readout applied to both disease models and matched controls under the same conditions?

**Primary readout** — the one measurement that decides it:
> Functional response of chaperone, co-chaperone, ubiquitin ligase and stress response biology (CHIP, HSF1) to the standardised stress, measured with one identical assay, timing and analysis framework across both disease arms and the shared control

The bridge is frozen for this phase at `bridge:46abfb23-533a8d87:v2` (v2),
evidence depth **`None`**, full-text review completed:
**none**. Every candidate below was
searched against that frozen question; the science was not adjusted to make the
search easier.

## Capability coverage

| Capability | Status | Candidate | Evidence | Recency |
| --- | --- | --- | --- | --- |
| Autosomal Recessive Spinocerebellar Ataxia 16  | `COVERED_SUPPORTED` | Bin Jiang | PMID:41851873 | CURRENT |
| Lafora Disease disease-relevant cellular model | `COVERED_SUPPORTED` | Robert G Gilbert | PMID:39245499 | CURRENT |
| Standardised cellular stress challenge | `COVERED_SUPPORTED` | Thomas Becker | PMID:39843636 | CURRENT |
| Functional assay reporting chaperone | `COVERED_SUPPORTED` | Claes Andréasson | PMID:38360885 | CURRENT |
| Secondary molecular profiling | `UNKNOWN` | — | — | — |

### What is missing or unknown
- **Secondary molecular profiling** — `UNKNOWN`. No sufficiently specific query could be built from the experiment's terms, so this capability was not searched. Unknown, not absent.

## How the searches were constrained

Every query is conjunctive, and a query returning more than **2,000** hits is
recorded as `TOO_BROAD_TO_IDENTIFY` and contributes no candidate.

That gate is not theoretical. The first run of this report ORed a bare protein
acronym into a disease query, returned **84,485 hits**, and marked the capability
covered on the strength of three authors who work on an unrelated condition that
shares the abbreviation. Two further capabilities returned over 120,000 hits of
unrelated biology. All three were reported as `COVERED_SUPPORTED`.

A result set that large means the search failed to discriminate, not that the
capability is abundant. Bare acronyms now never appear alone in a query, and a
capability with nothing to constrain it yields no query at all — recorded as
`UNKNOWN`, because no search is more honest than a search that cannot
discriminate.

## Historical versus current

| Recency | Meaning |
| --- | --- |
| `CURRENT` | demonstrated within 3 years |
| `RECENT` | within 8 years |
| `HISTORICAL` | older — not rejected, but requires current verification |

Historical evidence is never discarded. A group that ran an assay years ago may
still run it; the classification says what must be checked.

## Assets

`NO_RELEVANT_ASSET_IDENTIFIED`. No publication retrieved for the disease-model
capabilities described a model in terms specific enough to record as a reusable
asset. Where one is found in future, it will be recorded as
`MODEL_DEMONSTRATED` — a paper proves a model existed in that study, and proves
nothing about whether it is deposited, shareable or still maintained.

## Possible overlapping work

0 potential coordination opportunities.
None were substantiated: no group appeared with demonstrated capability across
more than one requirement, so there is no evidence of overlap to report. A
coordination opportunity requires evidence of actual overlap, and the object
refuses to be constructed without it. Nothing here is called duplication.

## What must be verified before contacting anyone

1. That the candidate still performs the assay — publication evidence is
   `TEAM_LEVEL` and historical by nature.
2. That a cellular model exists and is obtainable for **both** diseases.
3. That both models can be cultured identically; if they cannot, any difference
   is confounded by protocol rather than biology.
4. That the frozen bridge survives expert review, since it rests on
   abstract-level evidence and no one has read the full papers.

## The smallest plausible collaboration

`MULTI_PARTY_EXECUTABLE`. No single group is expected to hold a model of
each disease *and* the assay. The minimum is a group with the functional assay,
working with holders of each disease model, with secondary profiling optional
because it cannot decide the hypothesis.

**Capability is demonstrated. Willingness is `UNKNOWN` and is never inferred.**

