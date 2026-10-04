# Scientific assumptions and open implementation questions

Recorded: 2026-10-03.

- An explicit DisMech `downstream` record is imported as the curated source's
  causal/contributory assertion. It remains `UNREVIEWED` internally until the
  evidence-fit pipeline independently adjudicates it.
- A pathophysiology node without a computable biological scale is categorized
  `unspecified`; prose role names are not treated as claims.
- An edge target not present among imported pathophysiology or phenotype nodes
  is retained as an `unspecified` referenced node rather than dropped. This is
  a visible data-quality condition for later cross-section resolution.
- Legacy DisMech evidence polarity values are tolerated at the boundary, but
  only current normalized relations enter internal objects. Unknown values
  become neutral and require review; they are never upgraded to support.
- Missing `quote_role` becomes a database assertion with unknown source section,
  not a primary result.
- `HUMAN_CLINICAL` imports human species context. Other coarse DisMech evidence
  source values do not imply a species until resolved from the paper/model.
- Imported variant functional effect always defaults to `unknown` in this slice,
  even when consequence prose sounds predictive. A later validator will require
  evidence IDs before assigning loss/gain/dominant-negative or similar effects.
- Structural gap detection uses downstream reach only to find review candidates.
  It is not a scientific priority score and cannot claim missing evidence before
  mandatory source searches run.
- Current DisMech experiments and model-mechanism links are richer than the
  prompt's minimum. Their full typed import is the next adapter increment; the
  immutable source snapshot prevents loss in the meantime.
- The public Monarch v3 OpenAPI is treated as the integration contract. Live
  calls must be cached with response hashes/dates because endpoint and knowledge
  graph contents can change independently of this software.
- Demo-disease selection remains open until the candidate script runs against a
  current DisMech checkout. Candidate names in the upstream analysis are leads,
  not a preselected winner.

