"""Derive a KnowledgeGap and an ExperimentProposal from a refinement run.

The previous generator was a one-off: it hardcoded one SCAR16 claim id and
contained bespoke prose in every field, so it could not run on a second disease
at all. This module separates the two kinds of content that were tangled
together there:

* **Derived** -- everything recoverable from the refinement artifact: which claim
  is unresolved, what evidence played which role, which sibling claims are
  supported (and therefore outside the gap's scope), the search coverage, and all
  the identifier linkage. Generated, never authored.
* **Authored** -- the irreducibly scientific content: the exact question, why it
  matters, what kind of evidence is missing, the experiment design. Supplied by a
  per-run brief so it is explicit and reviewable rather than buried in code.

Keeping the split visible matters: a reader can see exactly which sentences the
software produced and which a person wrote, and the authored brief is a small
file a domain reviewer can check without reading Python.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from atlas.domain.claims import RefinementStatus
from atlas.domain.experiments import ExperimentProposal
from atlas.domain.gaps import (
    GapPriorityDimensions,
    GapType,
    KnowledgeGap,
    SearchCoverage,
)

OPEN_STATUSES = frozenset(
    {
        RefinementStatus.INSUFFICIENT_EVIDENCE,
        RefinementStatus.CONTEXT_DEPENDENT,
        RefinementStatus.CONTRADICTED,
        RefinementStatus.PARTIALLY_SUPPORTED,
    }
)

# Every interpretation a result of this kind cannot license, regardless of design.
UNIVERSAL_DISCLAIMERS: tuple[str, ...] = (
    "that any measured molecular difference demonstrates the cause of the "
    "clinical phenotype",
    "that an unchanged readout proves the alleles under test are benign",
    "that any result supports a therapeutic strategy or a clinical decision",
    "that results generalize to alleles, cell types or conditions not tested here",
)


class GapSynthesisError(ValueError):
    """The run does not support generating a gap for the requested claim."""


def _role_summary(atomic: Mapping[str, Any], role: str) -> str:
    references = atomic.get(role) or ()
    if not references:
        return "none"
    return "; ".join(str(item) for item in references)


def open_claims(refinement: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    """Atomic claims the synthesis left unresolved, in artifact order."""
    return tuple(
        atomic
        for atomic in refinement["atomic"]
        if RefinementStatus(atomic["status"]) in OPEN_STATUSES
    )


def build_gap(
    refinement: Mapping[str, Any],
    brief: Mapping[str, Any],
    *,
    claim_id: str,
    coverage: SearchCoverage,
) -> KnowledgeGap:
    """Build a gap for one unresolved claim.

    Refuses when the target claim is SUPPORTED: a gap must not be manufactured
    for a question the evidence already settles.
    """
    matches = [
        atomic for atomic in refinement["atomic"] if atomic["claim"]["claim_id"] == claim_id
    ]
    if not matches:
        raise GapSynthesisError(f"no atomic claim {claim_id!r} in this run")
    atomic = matches[0]
    status = RefinementStatus(atomic["status"])
    if status not in OPEN_STATUSES:
        raise GapSynthesisError(
            f"{claim_id} is {status.value}; refusing to manufacture a gap for a claim "
            "the evidence already settles"
        )

    supported = [
        item["claim"]["normalized_statement"]
        for item in refinement["atomic"]
        if RefinementStatus(item["status"]) is RefinementStatus.SUPPORTED
    ]
    siblings = [
        f"{item['claim']['normalized_statement']} [{item['status']}]"
        for item in refinement["atomic"]
        if item["claim"]["claim_id"] != claim_id
    ]

    # Derived: what the evidence actually did for this claim.
    current_evidence = (
        f"Synthesized {status.value} by rule {atomic['rule_applied']}. "
        f"Direct support: {_role_summary(atomic, 'direct_supporting')}. "
        f"Direct refutation: {_role_summary(atomic, 'direct_refuting')}. "
        f"Direct qualification: {_role_summary(atomic, 'direct_qualifying')}. "
        f"Indirect only: {_role_summary(atomic, 'indirect')}."
    )
    contradictory = (
        f"Background-only citations, which cannot set a status: "
        f"{_role_summary(atomic, 'background_only')}. "
        f"Qualifying evidence: {_role_summary(atomic, 'direct_qualifying')}. "
        f"Refuting evidence: {_role_summary(atomic, 'direct_refuting')}."
    )
    scope = (
        f"Applies to: {atomic['claim'].get('claim_scope') or claim_id}. "
        + (
            "Outside this gap, the run found supported: " + "; ".join(supported) + ". "
            if supported
            else "No sibling claim in this run reached SUPPORTED. "
        )
        + ("Sibling claim statuses: " + "; ".join(siblings) if siblings else "")
    ).strip()

    required = brief.get("priority_reason", {})
    return KnowledgeGap(
        gap_id=f"gap:{refinement['upstream_edge_id']}:{claim_id}",
        question=str(brief["question"]),
        gap_type=GapType(str(brief["gap_type"])),
        related_claims=(refinement["upstream_claim"]["claim_id"], claim_id),
        related_edges=(refinement["upstream_edge_id"],),
        scope=scope,
        why_it_matters=str(brief["why_it_matters"]),
        current_evidence_summary=current_evidence,
        contradictory_evidence_summary=contradictory,
        search_coverage=coverage,
        missing_evidence_type=tuple(brief["missing_evidence_type"]),
        required_context=tuple(brief["required_context"]),
        priority_reason=GapPriorityDimensions(
            causal_centrality=str(required["causal_centrality"]),
            downstream_dependence=str(required["downstream_dependence"]),
            evidence_conflict=str(required["evidence_conflict"]),
            translational_relevance=str(required["translational_relevance"]),
            experimental_tractability=str(required["experimental_tractability"]),
            available_assets=str(required["available_assets"]),
            discriminates_competing_hypotheses=str(
                required["discriminates_competing_hypotheses"]
            ),
        ),
        resolvability=str(brief["resolvability"]),
        proposed_discriminating_test=brief.get("proposed_discriminating_test"),
        status="OPEN",
    )


def build_experiment(
    gap: KnowledgeGap, design: Mapping[str, Any], *, extra_disclaimers: Sequence[str] = ()
) -> ExperimentProposal:
    """Build a falsifiable proposal from an authored design brief.

    The scientific question is taken from the gap rather than restated, so the
    two cannot drift apart, and the universal disclaimers are always appended to
    whatever the design declares.
    """
    disclaimers = tuple(
        dict.fromkeys(
            (
                *tuple(design.get("unjustified_interpretations") or ()),
                *UNIVERSAL_DISCLAIMERS,
                *extra_disclaimers,
            )
        )
    )
    return ExperimentProposal(
        experiment_id=f"experiment:{gap.gap_id}",
        knowledge_gap_id=gap.gap_id,
        scientific_question=gap.question,
        hypothesis=str(design["hypothesis"]),
        competing_hypothesis=str(design["competing_hypothesis"]),
        model_system=str(design["model_system"]),
        sample_type=str(design["sample_type"]),
        patient_stratification=tuple(design.get("patient_stratification") or ()),
        perturbation=str(design["perturbation"]),
        comparator=str(design["comparator"]),
        controls=tuple(design["controls"]),
        readouts=tuple(design["readouts"]),
        primary_endpoint=str(design["primary_endpoint"]),
        secondary_endpoints=tuple(design.get("secondary_endpoints") or ()),
        expected_result_if_supported=str(design["expected_result_if_supported"]),
        expected_result_if_refuted=str(design["expected_result_if_refuted"]),
        confounders=tuple(design["confounders"]),
        known_limitations=tuple(design["known_limitations"]),
        required_assets=tuple(design["required_assets"]),
        required_capabilities=tuple(design["required_capabilities"]),
        safety_or_ethics_flags=tuple(design.get("safety_or_ethics_flags") or ()),
        unjustified_interpretations=disclaimers,
    )
