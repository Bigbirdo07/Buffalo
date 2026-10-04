"""End-to-end invariants for the Goal 1 → Goal 3 → Goal 2 chain.

Asserts object lineage and the rules the chain depends on, never prose. Runs
against the committed artifacts, so it fails if a regeneration silently breaks a
link rather than only if a unit misbehaves.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GOAL1 = ROOT / "data/goals/goal1_scar16_neighbors.json"
GOAL3 = ROOT / "data/goals/goal3_flagship.json"
GOAL2 = ROOT / "data/goals/goal2_flagship.json"

pytestmark = pytest.mark.skipif(
    not (GOAL1.exists() and GOAL3.exists() and GOAL2.exists()),
    reason="goal artifacts not generated",
)


@pytest.fixture(scope="module")
def goals() -> tuple[dict, dict, dict]:
    return (
        json.loads(GOAL1.read_text()),
        json.loads(GOAL3.read_text()),
        json.loads(GOAL2.read_text()),
    )


class TestGoal1StartsFromADisease:
    def test_candidates_emerge_from_retrieval_not_selection(self, goals) -> None:
        one, _three, _two = goals
        assert one["candidates_retrieved"] > one["candidates_evaluated"]
        assert len(one["ranked"]) > 1
        # Ranks are dense and ordered: the list is a retrieval result, not a
        # hand-assembled set.
        assert [r["rank"] for r in one["ranked"]] == list(
            range(1, len(one["ranked"]) + 1)
        )

    def test_retrieval_and_validation_can_disagree(self, goals) -> None:
        one, _t, _tw = goals
        validities = {r["retrieval_validity"] for r in one["evaluated"]}
        relationships = {r["relationship"] for r in one["evaluated"]}
        # The whole product is that these are separate answers.
        assert len(validities) > 1, "every candidate got the same retrieval verdict"
        assert len(relationships) > 1, "every candidate got the same relationship"

    def test_outcome_spread_includes_rejections(self, goals) -> None:
        # A system that only confirms is not discriminating.
        one, _t, _tw = goals
        negative = {
            "INSUFFICIENT_EVIDENCE", "SHARED_PHENOTYPE_ONLY", "RETRIEVAL_ARTIFACT",
            "SHARED_TISSUE_CONTEXT", "SHARED_CELLULAR_PROCESS_NON_EQUIVALENT",
            "CONTRADICTED",
        }
        assert [r for r in one["evaluated"] if r["relationship"] in negative]

    def test_identity_excludes_some_candidates_from_discovery(self, goals) -> None:
        one, _t, _tw = goals
        excluded = [r for r in one["evaluated"] if not r["independent_discovery"]]
        assert excluded, "no identity or evidence exclusion occurred at all"

    def test_an_independent_relationship_survives(self, goals) -> None:
        one, _t, _tw = goals
        assert [r for r in one["evaluated"] if r["independent_discovery"]]


class TestGoal3DerivesFromValidatedBiology:
    def test_lineage_is_complete_and_ordered(self, goals) -> None:
        _o, three, _tw = goals
        lineage = three["lineage"]
        for key in (
            "sources", "validated_relationship", "mechanistic_bridge",
            "knowledge_gap", "experiment",
        ):
            assert lineage.get(key), f"lineage broken at {key}"

    def test_bridge_is_versioned_and_evidence_backed(self, goals) -> None:
        _o, three, _tw = goals
        assert three["lineage"]["bridge_version"] >= 1
        assert three["lineage"]["sources"]

    def test_evidence_depth_limitation_is_carried(self, goals) -> None:
        # The chain must not lose the fact that nobody read the full papers.
        _o, three, _tw = goals
        assert three["evidence_depth"]
        assert three["full_text_review_completed"] is False

    def test_experiment_is_falsifiable(self, goals) -> None:
        _o, three, _tw = goals
        experiment = three["experiment"]
        assert experiment["primary_readout"]
        assert experiment["expected_result_if_refuted"]
        assert (
            experiment["expected_result_if_refuted"]
            != experiment["expected_result_if_supported"]
        )
        assert experiment["competing_hypothesis"]
        assert experiment["human_review_required"]

    def test_gap_asks_about_the_bridge_not_the_retrieval_feature(self, goals) -> None:
        one, three, _tw = goals
        journey = json.loads(
            (ROOT / "data/flagship/flagship_journey.json").read_text()
        )
        question = three["knowledge_gap"]["question"].casefold()
        assert journey["retrieval_level_feature"].casefold() not in question


class TestGoal2BeginsFromTheExperiment:
    def test_search_is_driven_by_the_frozen_question(self, goals) -> None:
        _o, three, two = goals
        assert two["scientific_question"] == three["knowledge_gap"]["question"]

    def test_action_search_did_not_modify_the_science(self, goals) -> None:
        _o, three, two = goals
        assert two["frozen_bridge"]["terms"] == (
            json.loads((ROOT / "data/flagship/flagship_journey.json").read_text())[
                "validated_mechanistic_bridge"
            ]["terms"]
        )

    def test_capabilities_are_atomic_and_each_searched(self, goals) -> None:
        _o, _t, two = goals
        assert two["capabilities_total"] >= 3
        for row in two["capability_coverage"]:
            assert row["requirement_id"]
            assert row["why_required"]
            assert "searches" in row

    def test_scope_stays_conservative(self, goals) -> None:
        _o, _t, two = goals
        for row in two["capability_coverage"]:
            for team in row["candidate_teams"]:
                assert team["collaboration_willingness"] == "UNKNOWN"
                assert team["capability_verified"] is False

    def test_gaps_remain_visible(self, goals) -> None:
        _o, _t, two = goals
        assert (
            two["capabilities_covered"] + two["capabilities_missing"]
            <= two["capabilities_total"]
        )
        assert two["collaboration_topology"]

    def test_zero_coordination_is_an_accepted_outcome(self, goals) -> None:
        _o, _t, two = goals
        assert isinstance(two["potential_coordination_opportunities"], list)


class TestChainInvariants:
    """The rules the whole chain depends on, asserted together."""

    def test_candidate_is_not_a_validated_relationship(self, goals) -> None:
        one, _t, _tw = goals
        # Being retrieved does not make a pair a relationship: some retrieved
        # candidates carry a negative or identity outcome.
        evaluated = one["evaluated"]
        assert len([r for r in evaluated if r["independent_discovery"]]) < len(evaluated)

    def test_same_gene_is_not_same_mechanism(self, goals) -> None:
        one, _t, _tw = goals
        # The top-ranked hits share the anchor's gene and are excluded from
        # discovery by identity, not promoted by it.
        top = one["evaluated"][0]
        if top["identity"] in {"ALLELIC_SPECTRUM", "PARTIALLY_OVERLAPPING_ENTITY"}:
            assert not top["independent_discovery"]

    def test_mechanism_claims_carry_a_named_bridge(self, goals) -> None:
        one, _t, _tw = goals
        mechanistic = {
            "SHARED_CAUSAL_MECHANISM", "SHARED_DOWNSTREAM_MECHANISM",
            "SHARED_PROTEIN_COMPLEX", "SHARED_PATHWAY",
        }
        for row in one["evaluated"]:
            if row["relationship"] in mechanistic:
                assert row.get("bridge_terms"), (
                    f"{row['pair']} claims a shared mechanism with no named bridge"
                )

    def test_every_mechanism_claim_cites_evidence(self, goals) -> None:
        one, _t, _tw = goals
        mechanistic = {
            "SHARED_CAUSAL_MECHANISM", "SHARED_DOWNSTREAM_MECHANISM",
            "SHARED_PROTEIN_COMPLEX", "SHARED_PATHWAY",
        }
        for row in one["evaluated"]:
            if row["relationship"] in mechanistic:
                assert row.get("supporting_evidence"), (
                    f"{row['pair']} claims a mechanism with no evidence"
                )

    def test_search_coverage_is_recorded_for_every_candidate(self, goals) -> None:
        one, _t, _tw = goals
        for row in one["evaluated"]:
            assert row.get("search_coverage"), f"{row['pair']} has no coverage record"
