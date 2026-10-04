"""Tests for the generated SCAR16 action bundle.

These assert the properties that keep the bundle honest: no person-level claim is
asserted beyond its evidence, no execution clock leaks into the artifacts, no
contact data is copied out of source records, failed sources stay visible, and
the collaboration opportunity stays conservative.
"""

from __future__ import annotations

import json
import re
import unittest
from hashlib import sha256
from pathlib import Path

from atlas.domain.action import (
    CapabilityClaim,
    CapabilityClaimStatus,
    CapabilityDirectness,
    CollaborationOpportunity,
    RequiredAsset,
    RequiredCapability,
)
from atlas.domain.discovery import (
    AssetReuseStatus,
    ClinicalStudy,
    EntityResolutionDecision,
    EntityResolutionStatus,
    Grant,
    Laboratory,
    Organization,
    ResearchAsset,
    Researcher,
)
from atlas.domain.gaps import CoverageStatus, SearchCoverage
from atlas.domain.reviews import ScientificReviewStatus

ROOT = Path(__file__).parents[2]
BUNDLE = ROOT / "data" / "action" / "scar16_stub1_e3"
REFINEMENT = ROOT / "data" / "refinement" / "scar16_stub1_e3"


def _load(name: str) -> object:
    return json.loads((BUNDLE / name).read_text())


def _models(name: str, model: type) -> list:
    return [model.model_validate(item) for item in _load(name)]  # type: ignore[attr-defined]


class BundleSchemaTests(unittest.TestCase):
    def test_every_artifact_parses_through_its_strict_model(self) -> None:
        self.assertTrue(_models("required_capabilities.json", RequiredCapability))
        self.assertTrue(_models("required_assets.json", RequiredAsset))
        self.assertTrue(_models("researchers.json", Researcher))
        self.assertTrue(_models("laboratories.json", Laboratory))
        self.assertTrue(_models("capability_claims.json", CapabilityClaim))
        self.assertTrue(_models("research_assets.json", ResearchAsset))
        self.assertTrue(_models("grants.json", Grant))
        self.assertTrue(_models("clinical_studies.json", ClinicalStudy))
        self.assertTrue(_models("organizations.json", Organization))
        SearchCoverage.model_validate(_load("search_coverage.json"))
        CollaborationOpportunity.model_validate(_load("collaboration_opportunity.json"))

    def test_manifest_hashes_match_committed_artifacts(self) -> None:
        manifest = _load("reproducibility_manifest.json")
        assert isinstance(manifest, dict)
        for name, expected in manifest["artifact_sha256"].items():
            actual = sha256((BUNDLE / name).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, name)
        self.assertEqual(manifest["offline_rebuild"]["status"], "PASS")
        self.assertFalse(manifest["offline_rebuild"]["network_required"])
        for result in manifest["offline_rebuild"]["results"].values():
            self.assertTrue(result["byte_identical"])

    def test_manifest_pins_phase3_inputs(self) -> None:
        manifest = _load("reproducibility_manifest.json")
        assert isinstance(manifest, dict)
        for name, expected in manifest["phase3_inputs_sha256"].items():
            actual = sha256((REFINEMENT / name).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, name)


class DeterminismTests(unittest.TestCase):
    def test_no_execution_timestamp_leaks_into_the_bundle(self) -> None:
        """Every recorded instant must trace to the snapshot cache, not the clock."""
        lineage = _load("lineage.json")
        assert isinstance(lineage, dict)
        as_of = lineage["as_of"]
        self.assertRegex(as_of, r"^\d{4}-\d{2}-\d{2}$")
        self.assertIn("snapshot", lineage["as_of_basis"])
        coverage = SearchCoverage.model_validate(_load("search_coverage.json"))
        self.assertIsNotNone(coverage.search_completed_at)
        assert coverage.search_completed_at is not None
        self.assertEqual(coverage.search_completed_at.date().isoformat(), as_of)
        for source in coverage.sources:
            if source.checked_at is not None:
                self.assertEqual(source.checked_at.date().isoformat(), as_of)
        collaboration = CollaborationOpportunity.model_validate(
            _load("collaboration_opportunity.json")
        )
        self.assertEqual(collaboration.created_at.date().isoformat(), as_of)
        for claim in _models("capability_claims.json", CapabilityClaim):
            self.assertEqual(claim.last_checked.isoformat(), as_of)


class PersonalDataTests(unittest.TestCase):
    EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

    def test_no_email_address_is_copied_into_any_artifact(self) -> None:
        for path in sorted(BUNDLE.glob("*.json")):
            text = path.read_text()
            self.assertIsNone(self.EMAIL.search(text), f"{path.name} contains an email")

    def test_no_contact_preamble_survives_affiliation_cleaning(self) -> None:
        for person in _models("researchers.json", Researcher):
            if person.institution:
                self.assertNotIn("electronic address", person.institution.lower())
            self.assertIsNone(person.email)

    def test_api_tokens_are_never_written_to_artifacts_or_snapshots(self) -> None:
        pattern = re.compile(r"BRIGHTDATA_API_TOKEN\s*[=:]\s*\S+|Bearer\s+[A-Za-z0-9._-]{12,}")
        for path in sorted(BUNDLE.rglob("*.json")):
            self.assertIsNone(pattern.search(path.read_text()), path.name)


class SubjectClaimTests(unittest.TestCase):
    def test_researchers_are_derived_with_provenance_to_a_source_record(self) -> None:
        people = _models("researchers.json", Researcher)
        self.assertTrue(people)
        for person in people:
            self.assertTrue(person.provenance, person.researcher_id)
            for reference in person.provenance:
                self.assertEqual(reference.source_type, "PubMed")
                self.assertRegex(reference.source_id, r"^PMID:\d+$")
                self.assertRegex(reference.snapshot_sha256 or "", r"^[0-9a-f]{64}$")
            self.assertTrue(person.publications)

    def test_researcher_role_does_not_assert_current_employment(self) -> None:
        for person in _models("researchers.json", Researcher):
            self.assertIsNotNone(person.role)
            assert person.role is not None
            self.assertIn("unverified", person.role.lower())

    def test_no_personal_capability_claim_is_asserted(self) -> None:
        """Publication authorship is team-level evidence, so subjects stay teams."""
        for claim in _models("capability_claims.json", CapabilityClaim):
            self.assertEqual(claim.subject_type, "laboratory")
            self.assertNotEqual(claim.directness, CapabilityDirectness.DIRECT)

    def test_author_groups_claim_no_verified_official_website(self) -> None:
        for lab in _models("laboratories.json", Laboratory):
            self.assertIsNone(lab.official_url)
            self.assertTrue(lab.provenance)

    def test_identifiers_are_ascii_while_names_stay_verbatim(self) -> None:
        people = _models("researchers.json", Researcher)
        self.assertTrue(any("ö" in person.canonical_name for person in people))
        for person in people:
            self.assertTrue(person.researcher_id.isascii(), person.researcher_id)

    def test_ambiguous_identities_are_flagged_and_not_merged(self) -> None:
        decisions = _models("entity_resolution.json", EntityResolutionDecision)
        possible = [
            item
            for item in decisions
            if item.status is EntityResolutionStatus.POSSIBLE_DUPLICATE
        ]
        self.assertTrue(possible, "abbreviated forenames must raise a duplicate question")
        ids = {person.researcher_id for person in _models("researchers.json", Researcher)}
        for decision in possible:
            self.assertIn(decision.left_entity_id, ids)
            self.assertIn(decision.right_entity_id, ids)
            self.assertNotEqual(decision.left_entity_id, decision.right_entity_id)
            self.assertIn("not merged", decision.rationale)
            self.assertEqual(decision.human_review_status, ScientificReviewStatus.PENDING)


class CapabilityEvidenceTests(unittest.TestCase):
    def test_historical_publication_evidence_is_classified_outdated(self) -> None:
        claims = {
            claim.claim_id: claim for claim in _models("capability_claims.json", CapabilityClaim)
        }
        ipsc = [claim for claim in claims.values() if "scar16-patient-ipsc" in claim.claim_id]
        self.assertTrue(ipsc)
        for claim in ipsc:
            self.assertEqual(claim.status, CapabilityClaimStatus.OUTDATED)
            self.assertEqual(claim.recency, "historical_or_unknown")

    def test_single_source_type_cannot_reach_verified(self) -> None:
        for claim in _models("capability_claims.json", CapabilityClaim):
            if len(set(claim.evidence_source_types)) < 2:
                self.assertNotEqual(claim.status, CapabilityClaimStatus.VERIFIED)

    def test_every_claim_carries_evidence_and_a_rationale(self) -> None:
        for claim in _models("capability_claims.json", CapabilityClaim):
            self.assertTrue(claim.rationale)
            self.assertEqual(claim.human_review_status, ScientificReviewStatus.PENDING)
            if claim.status in {
                CapabilityClaimStatus.VERIFIED,
                CapabilityClaimStatus.SUPPORTED,
                CapabilityClaimStatus.OUTDATED,
            }:
                self.assertTrue(claim.evidence_items, claim.claim_id)

    def test_context_mismatched_grants_are_retained_but_unused(self) -> None:
        lineage = _load("lineage.json")
        assert isinstance(lineage, dict)
        considered = lineage["grants_considered"]
        self.assertTrue(considered)
        used = [item for item in considered if item["used_as_capability_evidence"]]
        self.assertEqual(used, [], "no retrieved grant satisfies the strict relevance rule")
        for item in considered:
            self.assertTrue(item["disposition"])
        dispositions = {item["disposition"].split(":")[0] for item in considered}
        self.assertIn("CONTEXT_MISMATCH", dispositions)

    def test_no_grant_signal_is_promoted_to_personal_capability(self) -> None:
        claims = _models("capability_claims.json", CapabilityClaim)
        grant_ids = {item.grant_id for item in _models("grants.json", Grant)}
        for claim in claims:
            self.assertFalse(set(claim.evidence_items) & grant_ids)


class AssetQualificationTests(unittest.TestCase):
    def test_no_asset_is_marked_validated_for_the_target_context(self) -> None:
        for asset in _models("research_assets.json", ResearchAsset):
            self.assertNotEqual(
                asset.reuse_status, AssetReuseStatus.VALIDATED_FOR_TARGET_CONTEXT
            )
            self.assertEqual(asset.reuse_status, AssetReuseStatus.REQUIRES_VALIDATION)
            self.assertTrue(asset.evidence)
            self.assertTrue(asset.availability)

    def test_variant_mismatch_is_stated_for_the_patient_ipsc_line(self) -> None:
        assets = {item.asset_id: item for item in _models("research_assets.json", ResearchAsset)}
        line = assets["asset:stub1-patient-ipsc:pmid-29679845"]
        joined = " ".join(line.variant_context).lower()
        self.assertIn("k145q", joined)
        self.assertIn("m211i", joined)
        self.assertIn("unknown", line.availability.lower())

    def test_registry_asset_is_not_treated_as_mechanistic_capability(self) -> None:
        studies = _models("clinical_studies.json", ClinicalStudy)
        self.assertTrue(studies)
        coverage = SearchCoverage.model_validate(_load("search_coverage.json"))
        trial_source = next(
            item for item in coverage.sources if item.source == "ClinicalTrials.gov"
        )
        self.assertEqual(trial_source.status, CoverageStatus.CHECKED)
        claims = _models("capability_claims.json", CapabilityClaim)
        study_ids = {item.study_id for item in studies}
        for claim in claims:
            self.assertFalse(set(claim.evidence_items) & study_ids)

    def test_patient_organization_is_recorded_without_inferred_services(self) -> None:
        organizations = _models("organizations.json", Organization)
        self.assertTrue(organizations)
        for organization in organizations:
            self.assertTrue(organization.provenance)
            self.assertIsNotNone(organization.contact_source)
            assert organization.contact_source is not None
            self.assertIn("no direct contact route", organization.contact_source)


class CoverageHonestyTests(unittest.TestCase):
    def test_failed_and_unattempted_sources_remain_visible(self) -> None:
        coverage = SearchCoverage.model_validate(_load("search_coverage.json"))
        by_status: dict[CoverageStatus, list[str]] = {}
        for source in coverage.sources:
            by_status.setdefault(source.status, []).append(source.source)
        self.assertIn(CoverageStatus.FAILED, by_status)
        self.assertIn(CoverageStatus.NOT_STARTED, by_status)
        self.assertIn("Bright Data", by_status[CoverageStatus.FAILED])

    def test_a_failed_source_never_reports_zero_results(self) -> None:
        coverage = SearchCoverage.model_validate(_load("search_coverage.json"))
        for source in coverage.sources:
            if source.status in {CoverageStatus.FAILED, CoverageStatus.NOT_STARTED}:
                self.assertIsNone(
                    source.result_count,
                    f"{source.source} must not claim a count it never obtained",
                )

    def test_failed_sources_record_a_reason(self) -> None:
        coverage = SearchCoverage.model_validate(_load("search_coverage.json"))
        for source in coverage.sources:
            if source.status is CoverageStatus.FAILED:
                self.assertTrue(source.error, source.source)

    def test_checked_sources_record_queries_counts_and_snapshots(self) -> None:
        coverage = SearchCoverage.model_validate(_load("search_coverage.json"))
        checked = [
            item for item in coverage.sources if item.status is CoverageStatus.CHECKED
        ]
        self.assertGreaterEqual(len(checked), 3)
        for source in checked:
            self.assertTrue(source.queries, source.source)
            self.assertIsNotNone(source.result_count)
            self.assertTrue(source.snapshot_references, source.source)

    def test_absence_language_is_qualified(self) -> None:
        coverage = SearchCoverage.model_validate(_load("search_coverage.json"))
        caveat = coverage.interpretation_caveat.lower()
        self.assertIn("not evidence", caveat)
        self.assertIn("successfully searched", caveat)
        self.assertTrue(coverage.language_limitations)
        self.assertTrue(coverage.geographic_limitations)


class CollaborationConservatismTests(unittest.TestCase):
    def setUp(self) -> None:
        self.collaboration = CollaborationOpportunity.model_validate(
            _load("collaboration_opportunity.json")
        )

    def test_status_is_not_ready_while_capabilities_are_missing(self) -> None:
        self.assertTrue(self.collaboration.missing_capabilities)
        self.assertEqual(self.collaboration.status.value, "MISSING_CAPABILITY")

    def test_missing_capabilities_are_exposed_by_name(self) -> None:
        explanation = _load("scientist_explanation.json")
        assert isinstance(explanation, dict)
        self.assertEqual(
            set(explanation["missing_capabilities"]),
            set(self.collaboration.missing_capabilities),
        )
        self.assertTrue(explanation["missing_capability_names"])

    def test_required_capabilities_are_either_provided_or_listed_missing(self) -> None:
        required = {item.capability_id for item in _models(
            "required_capabilities.json", RequiredCapability
        )}
        accounted = set(self.collaboration.provided_capabilities) | set(
            self.collaboration.missing_capabilities
        )
        self.assertEqual(required, accounted)

    def test_no_contact_target_is_asserted_without_verification(self) -> None:
        self.assertIsNone(self.collaboration.first_contact_target)

    def test_uncertainties_name_the_specific_unverified_facts(self) -> None:
        joined = " ".join(self.collaboration.uncertainties).lower()
        for expected in ("affiliation", "willingness", "digly", "editing"):
            self.assertIn(expected, joined)

    def test_duplication_is_not_asserted_without_program_data(self) -> None:
        self.assertIn("NOT ASSESSED", self.collaboration.duplication_risk)

    def test_only_usable_claims_contribute_provided_capabilities(self) -> None:
        """A capability is provided only if some subject has a usable claim for it.

        The same capability can be OUTDATED for one group and SUPPORTED by another,
        so the invariant is per capability rather than per claim.
        """
        claims = _models("capability_claims.json", CapabilityClaim)
        usable = {
            claim.capability_id
            for claim in claims
            if claim.status
            in {CapabilityClaimStatus.VERIFIED, CapabilityClaimStatus.SUPPORTED}
        }
        self.assertEqual(set(self.collaboration.provided_capabilities), usable)

    def test_a_capability_with_only_outdated_claims_is_not_provided(self) -> None:
        claims = _models("capability_claims.json", CapabilityClaim)
        by_capability: dict[str, set[CapabilityClaimStatus]] = {}
        for claim in claims:
            by_capability.setdefault(claim.capability_id, set()).add(claim.status)
        only_outdated = {
            capability_id
            for capability_id, statuses in by_capability.items()
            if statuses == {CapabilityClaimStatus.OUTDATED}
        }
        self.assertTrue(only_outdated, "this bundle has a wholly historical capability")
        self.assertFalse(only_outdated & set(self.collaboration.provided_capabilities))


class TargetedDiscoveryTests(unittest.TestCase):
    """The tiered capability search must not let technique imply disease expertise."""

    def setUp(self) -> None:
        self.search = _load("capability_search.json")
        assert isinstance(self.search, dict)

    def test_only_a_curated_subset_of_queries_was_executed(self) -> None:
        generated = _load("discovery_queries.json")
        assert isinstance(generated, list)
        executed = self.search["executed"]
        self.assertTrue(executed)
        self.assertLess(
            len(executed), len(generated) // 4, "the full generated set must not be run"
        )

    def test_both_query_tiers_are_declared_and_used(self) -> None:
        tiers = {item["tier"] for item in self.search["executed"]}
        self.assertIn("A_disease_anchored", tiers)
        self.assertIn("B_capability_anchored", tiers)
        self.assertIn("A_disease_anchored", self.search["tiers"])

    def test_every_executed_query_records_hits_and_a_snapshot(self) -> None:
        for item in self.search["executed"]:
            self.assertIsInstance(item["total_hits"], int)
            self.assertRegex(item["snapshot_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(item["rationale"])

    def test_unpromoted_leads_remain_recorded(self) -> None:
        retrieved = {
            pmid for item in self.search["executed"] for pmid in item["retrieved_pmids"]
        }
        selected = {item["pmid"] for item in self.search["candidates_selected"]}
        self.assertTrue(selected <= retrieved)
        self.assertTrue(
            retrieved - selected, "leads not promoted must still be visible to a reviewer"
        )
        self.assertTrue(self.search["selection_rule"])

    def test_capability_anchored_candidates_disclaim_disease_involvement(self) -> None:
        anchored = [
            item
            for item in self.search["candidates_selected"]
            if item["tier"] == "B_capability_anchored"
        ]
        self.assertTrue(anchored)
        for item in anchored:
            self.assertIn("no STUB1 or SCAR16 involvement", item["disease_involvement"])
            self.assertIn("not evidence of disease involvement", item["limitation"])

    def test_candidate_participants_state_the_absence_of_disease_involvement(self) -> None:
        collaboration = CollaborationOpportunity.model_validate(
            _load("collaboration_opportunity.json")
        )
        candidate_roles = [
            item.proposed_role
            for item in collaboration.participants
            if item.subject_id.startswith("capability-candidate:")
        ]
        self.assertTrue(candidate_roles)
        for role in candidate_roles:
            self.assertIn("no STUB1 or SCAR16 involvement established", role)
            self.assertIn("verified", role)

    def test_candidate_claims_never_exceed_supported(self) -> None:
        for claim in _models("capability_claims.json", CapabilityClaim):
            if claim.subject_id.startswith("capability-candidate:"):
                self.assertNotEqual(claim.status, CapabilityClaimStatus.VERIFIED)
                self.assertEqual(claim.directness, CapabilityDirectness.TEAM_LEVEL)


if __name__ == "__main__":
    unittest.main()
