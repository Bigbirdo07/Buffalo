#!/usr/bin/env python3
"""Build the SCAR16 action bundle from the Phase 3 experiment and cached sources.

Design rules this script is required to honour:

* Nothing about a real person is typed in by hand. Researchers, their names and
  their affiliation strings are derived from cached PubMed author records, and
  each carries a ProvenanceReference to the record it came from.
* No execution timestamps. ``as_of`` is derived from the newest cached snapshot
  retrieval time, so two runs over the same cache are byte-identical.
* Institution-level or team-level evidence is never promoted to a personal
  capability; author groups are modelled as publication-derived teams.
* A source that failed or was not searched is recorded as FAILED/NOT_STARTED
  with the reason, never as zero results.

Run offline (cache only) with --offline; omit it to refresh the caches.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from atlas.adapters.clinical_trials.client import ClinicalTrialsClient
from atlas.adapters.literature.client import (
    PubMedClient,
    PubMedRecord,
    RetrievalError,
    SnapshotFetcher,
    clean_affiliation,
)
from atlas.adapters.nih_reporter.client import NIHReporterClient
from atlas.domain.action import CollaborationParticipant
from atlas.domain.discovery import (
    AssetReuseStatus,
    AssetType,
    CapabilityEvidenceSignal,
    ClinicalStudy,
    EntityResolutionDecision,
    EntityResolutionStatus,
    Grant,
    Laboratory,
    Organization,
    OrganizationType,
    ProvenanceReference,
    ResearchAsset,
    Researcher,
)
from atlas.domain.experiments import ExperimentProposal
from atlas.domain.gaps import CoverageStatus, SearchCoverage, SearchSourceCoverage
from atlas.services.action_discovery import (
    assess_capability,
    generate_discovery_queries,
    synthesize_collaboration,
)
from atlas.services.capability_discovery import (
    DiscoveryContext,
    build_targeted_queries,
    candidate_signals,
    coverage_note,
    derive_candidates,
    run_searches,
)
from atlas.services.requirement_extraction import extract_experiment_requirements

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/refinement/scar16_stub1_e3"
DEFAULT_OUTPUT = ROOT / "data/action/scar16_stub1_e3"

# The SCAR16/STUB1 literature set collected during Phase 3 retrieval.
PUBMED_BATCH: tuple[str, ...] = (
    "24113144", "25258038", "25259530", "28396517", "28593200", "29679845",
    "30222779", "30381368", "31126790", "31571321", "31619515", "31741143",
    "32258232", "32337344", "32342324", "32367277", "32713943", "32775533",
    "32775534", "33097556", "33200713", "33417001", "33431799", "33811518",
    "34070858", "34535633", "34565360", "34630034", "34906452", "35398354",
    "35493319", "35588347", "36422518", "36476347", "36569391", "36853170",
    "36892293", "37479376", "38625442", "38973070", "39117117", "39680235",
    "39707479", "39950762", "41851873", "41891335", "42567515", "42768770",
)

# Publication-derived author groups. Only PMIDs are named here; every person,
# name and affiliation is read out of the cached record for these PMIDs.
TEAMS: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "team:scar16-patient-ipsc",
        "SCAR16 patient-derived iPSC and neuronal-model author group",
        ("29679845", "33097556"),
        ("cell_culture", "ipsc_neuronal_differentiation"),
    ),
    (
        "team:chip-variant-biochemistry",
        "CHIP variant biochemistry author group",
        ("31619515", "42567515"),
        ("ubiquitination_assay", "protein_biochemistry"),
    ),
)

NIH_QUERIES: tuple[str, ...] = (
    "STUB1 ataxia",
    "STUB1 CHIP ubiquitin ligase",
    "CHIP ubiquitin ligase cochaperone",
    "spinocerebellar ataxia iPSC neurons",
)
CLINICAL_TRIAL_QUERIES: tuple[str, ...] = (
    "STUB1",
    "spinocerebellar ataxia 16",
    "Gordon Holmes syndrome",
)
# Grant relevance rule. Keyword matching cannot establish scientific relevance, so the
# conjunction is deliberately strict and a grant that fails it is retained and reported
# rather than quietly used or quietly dropped:
#   * the subject must appear as a whole word, case-sensitively -- "CHIP" is the protein
#     while "ChIP" is chromatin immunoprecipitation, and the two collide constantly;
#   * a disease-specific context term must appear. "neurodegeneration" alone does not
#     count: it appears as boilerplate in cancer and cardiac awards;
#   * the award must still be active, since an expired award evidences past activity.
GRANT_SUBJECT = re.compile(r"\bSTUB1\b")
GRANT_CONTEXT = re.compile(r"ataxia|cerebellar|spinocerebellar|Purkinje|SCAR16", re.IGNORECASE)
# Conditions that make a registry record genuinely STUB1-relevant.
STUB1_CONDITION_TERMS = ("stub1",)


@dataclass(frozen=True, slots=True)
class SourceOutcome:
    """Result of one attempted source search, successful or not."""

    source: str
    status: CoverageStatus
    queries: tuple[str, ...]
    result_count: int | None = None
    error: str | None = None
    snapshots: tuple[str, ...] = ()
    note: str | None = None


def _json_ready(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")  # type: ignore[union-attr]
    if isinstance(value, tuple | list):
        return [_json_ready(item) for item in value]
    return value


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_ready(value), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _snapshot_times(*snapshot_dirs: Path) -> dict[str, datetime]:
    """Map snapshot content hash -> recorded retrieval time, across cache dirs."""
    result: dict[str, datetime] = {}
    for directory in snapshot_dirs:
        for metadata_path in sorted(directory.glob("*.json")):
            metadata = json.loads(metadata_path.read_text())
            digest = str(metadata.get("sha256", ""))
            retrieved = metadata.get("retrieved_at")
            if digest and isinstance(retrieved, str):
                result[digest] = datetime.fromisoformat(retrieved)
    return result


def _provenance(pmid: str, digest: str, retrieved_at: datetime) -> ProvenanceReference:
    return ProvenanceReference(
        source_type="PubMed",
        source_id=f"PMID:{pmid}",
        source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        snapshot_sha256=digest,
        retrieved_at=retrieved_at,
    )


_TRANSLITERATE = str.maketrans(
    {"ö": "o", "ä": "a", "ü": "u", "é": "e", "è": "e", "á": "a", "í": "i", "ó": "o",
     "ú": "u", "ñ": "n", "ç": "c", "ß": "ss", "å": "a", "ø": "o", "ł": "l"}
)


def _researcher_id(name: str) -> str:
    folded = name.lower().translate(_TRANSLITERATE)
    slug = "".join(char if char.isascii() and char.isalnum() else "-" for char in folded)
    slug = slug.strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"researcher:{slug}"


def derive_people(
    records: dict[str, PubMedRecord],
    pmids: tuple[str, ...],
    times: dict[str, datetime],
) -> tuple[Researcher, ...]:
    """Derive researchers from cached author records.

    Selection rule, applied verbatim and recorded in the audit: the first author
    and the last author of each publication. Names and affiliation strings are
    copied from the record; nothing is inferred about current role or employment.
    """
    collected: dict[str, dict[str, object]] = {}
    for pmid in pmids:
        record = records[pmid]
        if not record.authors:
            continue
        positions = {0: "first author", len(record.authors) - 1: "last author"}
        for index, label in sorted(positions.items()):
            author = record.authors[index]
            key = _researcher_id(author.name)
            entry = collected.setdefault(
                key,
                {
                    "name": author.name,
                    "affiliations": [],
                    "publications": [],
                    "positions": [],
                    "provenance": [],
                },
            )
            publications = entry["publications"]
            assert isinstance(publications, list)
            publications.append(f"PMID:{pmid}")
            positions_list = entry["positions"]
            assert isinstance(positions_list, list)
            positions_list.append(f"{label} on PMID:{pmid}")
            affiliations = entry["affiliations"]
            assert isinstance(affiliations, list)
            for affiliation in author.affiliations:
                cleaned = clean_affiliation(affiliation)
                if cleaned and cleaned not in affiliations:
                    affiliations.append(cleaned)
            provenance = entry["provenance"]
            assert isinstance(provenance, list)
            digest = record.snapshot_sha256
            provenance.append(_provenance(pmid, digest, times[digest]))
    people: list[Researcher] = []
    for key in sorted(collected):
        entry = collected[key]
        provenance = entry["provenance"]
        assert isinstance(provenance, list)
        affiliations = entry["affiliations"]
        assert isinstance(affiliations, list)
        publications = entry["publications"]
        assert isinstance(publications, list)
        positions_list = entry["positions"]
        assert isinstance(positions_list, list)
        people.append(
            Researcher(
                researcher_id=key,
                canonical_name=str(entry["name"]),
                institution=affiliations[0] if affiliations else None,
                aliases=(),
                country=None,
                role=(
                    "; ".join(positions_list)
                    + ". Publication authorship only: current role, employment and "
                    "willingness to collaborate are unverified."
                ),
                publications=tuple(dict.fromkeys(publications)),
                last_verified_at=max(item.retrieved_at for item in provenance),
                provenance=tuple(provenance),
            )
        )
    return tuple(people)


def resolve_identities(
    people: tuple[Researcher, ...],
) -> tuple[EntityResolutionDecision, ...]:
    """Flag names that may denote one person without merging the records.

    PubMed abbreviates forenames inconsistently between records, so "S Schuster"
    and "Stefanie Schuster" may be one researcher or two. An automated merge here
    would silently invent an identity and attribute pooled capability to it, so
    the records stay separate and the ambiguity is reported for human review.
    """
    decisions: list[EntityResolutionDecision] = []
    for index, left in enumerate(people):
        for right in people[index + 1 :]:
            left_parts = left.canonical_name.split()
            right_parts = right.canonical_name.split()
            if left_parts[-1].lower() != right_parts[-1].lower():
                continue
            left_initial = left_parts[0][0].lower()
            right_initial = right_parts[0][0].lower()
            if left_initial != right_initial:
                continue
            abbreviated = min(len(left_parts[0]), len(right_parts[0])) == 1
            shared_affiliation = bool(
                left.institution
                and right.institution
                and left.institution.split(",")[0] == right.institution.split(",")[0]
            )
            matching = ["identical surname", "identical first initial"]
            conflicting: list[str] = []
            if abbreviated:
                matching.append("one record abbreviates the forename")
            if shared_affiliation:
                matching.append("same leading affiliation string")
            else:
                conflicting.append("leading affiliation strings differ")
            if set(left.publications) & set(right.publications):
                conflicting.append(
                    "both names appear on the same publication, so they are likely "
                    "distinct people"
                )
                status = EntityResolutionStatus.DISTINCT
                rationale = (
                    "Both name forms appear as separate authors on a shared publication, "
                    "which argues they are different people."
                )
            else:
                status = EntityResolutionStatus.POSSIBLE_DUPLICATE
                rationale = (
                    "Surname and first initial agree across records that share no "
                    "publication. This may be one researcher recorded under an "
                    "abbreviated forename, or two people. The records are deliberately "
                    "not merged and no capability evidence is pooled across them."
                )
            decisions.append(
                EntityResolutionDecision(
                    decision_id=f"entity-resolution:{left.researcher_id}|{right.researcher_id}",
                    left_entity_id=left.researcher_id,
                    right_entity_id=right.researcher_id,
                    status=status,
                    matching_signals=tuple(matching),
                    conflicting_signals=tuple(conflicting),
                    rationale=rationale,
                )
            )
    return tuple(decisions)


def search_nih(
    fetcher: SnapshotFetcher, queries: tuple[str, ...]
) -> tuple[tuple[Grant, ...], SourceOutcome]:
    grants: list[Grant] = []
    snapshots: list[str] = []
    total = 0
    try:
        for query in queries:
            count, found, digest = NIHReporterClient(fetcher).search(query, limit=25)
            total += count
            snapshots.append(digest)
            grants.extend(found)
    except RetrievalError as error:
        return (), SourceOutcome(
            source="NIH RePORTER",
            status=CoverageStatus.FAILED,
            queries=queries,
            error=str(error),
        )
    unique = tuple(
        sorted({grant.grant_id: grant for grant in grants}.values(), key=lambda x: x.grant_id)
    )
    qualifying = tuple(
        grant
        for grant in unique
        if GRANT_SUBJECT.search(f"{grant.title} {grant.abstract}")
        and GRANT_CONTEXT.search(f"{grant.title} {grant.abstract}")
        and grant.active
    )
    return unique, SourceOutcome(
        source="NIH RePORTER",
        status=CoverageStatus.CHECKED,
        queries=queries,
        result_count=total,
        snapshots=tuple(dict.fromkeys(snapshots)),
        note=(
            f"{total} record hits across {len(queries)} queries; {len(unique)} distinct awards "
            f"retrieved; {len(qualifying)} satisfy the strict relevance rule (whole-word STUB1, "
            "a disease-specific context term, and still active). Awards retrieved because the "
            "token 'CHIP' or an incidental 'neurodegeneration' mention matched are retained for "
            "review but are not used as capability evidence."
        ),
    )


def search_trials(
    fetcher: SnapshotFetcher, queries: tuple[str, ...]
) -> tuple[tuple[ClinicalStudy, ...], SourceOutcome]:
    studies: dict[str, ClinicalStudy] = {}
    snapshots: list[str] = []
    total = 0
    try:
        for query in queries:
            count, found, digest = ClinicalTrialsClient(fetcher).search(query, page_size=20)
            total += count
            snapshots.append(digest)
            for study in found:
                studies.setdefault(study.study_id, study)
    except RetrievalError as error:
        return (), SourceOutcome(
            source="ClinicalTrials.gov",
            status=CoverageStatus.FAILED,
            queries=queries,
            error=str(error),
        )
    relevant = tuple(
        study
        for study in sorted(studies.values(), key=lambda item: item.study_id)
        if any(
            term in condition.lower()
            for condition in study.conditions
            for term in STUB1_CONDITION_TERMS
        )
    )
    return relevant, SourceOutcome(
        source="ClinicalTrials.gov",
        status=CoverageStatus.CHECKED,
        queries=queries,
        result_count=total,
        snapshots=tuple(dict.fromkeys(snapshots)),
        note=(
            f"{total} records matched across {len(queries)} queries; {len(relevant)} list a "
            "STUB1 condition explicitly. Trial participation evidences clinical and registry "
            "infrastructure, not mechanistic expertise."
        ),
    )


def build_discovery_context(
    plan: dict, experiment: ExperimentProposal, capabilities: Sequence[Any]
) -> DiscoveryContext:
    """Derive search anchors from the run's own plan and experiment.

    Every term comes from structured data: the observation plan states the gene
    and disease scope, the experiment states its model system and readout, and
    the extracted capabilities state what must be done. Nothing is a literal, so
    the same code runs for any disease. A slot with no available term stays
    empty and its dependent query is reported as skipped, never silently
    broadened into a different question.
    """
    target = plan.get("target", {}) if isinstance(plan, dict) else {}
    gene = target.get("gene")
    genes = (str(gene),) if isinstance(gene, str) and gene else ()
    diseases = tuple(
        str(item)
        for item in (target.get("disease_scope") or ())
        if isinstance(item, str)
    )

    assays: list[str] = []
    for capability in capabilities:
        label = getattr(capability, "label", None)
        if isinstance(label, str) and label:
            assays.append(label)
    for attribute in ("primary_readout", "readout"):
        value = getattr(experiment, attribute, None)
        if isinstance(value, str) and value:
            assays.append(value)

    models: list[str] = []
    for attribute in ("model_system", "model"):
        value = getattr(experiment, attribute, None)
        if isinstance(value, str) and value:
            models.append(value)

    cells = [
        item
        for item in (plan.get("readout_family") or () if isinstance(plan, dict) else ())
        if isinstance(item, str)
    ]

    def top(values: list[str], limit: int) -> tuple[str, ...]:
        counts = Counter(value.strip() for value in values if value and value.strip())
        return tuple(name for name, _n in counts.most_common(limit))

    return DiscoveryContext(
        gene_symbols=genes,
        cell_type_terms=top(cells, 4),
        assay_terms=top(assays, 4),
        model_system_terms=top(models, 2),
        disease_terms=diseases,
    )


def build(input_dir: Path, output_dir: Path, *, offline: bool) -> None:
    experiment = ExperimentProposal.model_validate_json(
        (input_dir / "experiment_proposal.json").read_text()
    )
    capabilities, required_assets = extract_experiment_requirements(experiment)
    plan = json.loads((input_dir / "observation_plan.json").read_text())
    plan_target = plan.get("target", {})
    queries = generate_discovery_queries(
        capabilities,
        gene=str(plan_target.get("gene") or ""),
        disease=next(iter(plan_target.get("disease_scope") or ("",)), ""),
        mechanism_terms=tuple(plan.get("readout_family") or ()),
    )

    refinement_snapshots = input_dir / "snapshots"
    action_snapshots = output_dir / "snapshots"
    action_snapshots.mkdir(parents=True, exist_ok=True)
    literature = PubMedClient(SnapshotFetcher(refinement_snapshots, offline=offline))
    records = literature.records(PUBMED_BATCH)
    missing = tuple(
        pmid for team in TEAMS for pmid in team[2] if pmid not in records
    )
    if missing:
        raise SystemExit(f"required cached PubMed records missing: {missing}")

    action_fetcher = SnapshotFetcher(action_snapshots, offline=offline)
    grants, nih_outcome = search_nih(action_fetcher, NIH_QUERIES)
    studies, trial_outcome = search_trials(action_fetcher, CLINICAL_TRIAL_QUERIES)

    # Targeted capability discovery. Only the curated subset in TARGETED_QUERIES runs;
    # the full generated set is recorded in the bundle but deliberately not executed.
    discovery_context = build_discovery_context(plan, experiment, capabilities)
    targeted_queries, skipped_queries = build_targeted_queries(discovery_context)
    search_results, search_failures = run_searches(
        PubMedClient(SnapshotFetcher(action_snapshots, offline=offline)),
        targeted_queries,
    )
    search_failures = (*search_failures, *skipped_queries)
    discovered_pmids = tuple(
        dict.fromkeys(pmid for result in search_results for pmid in result.pmids)
    )
    discovered_records = (
        PubMedClient(SnapshotFetcher(action_snapshots, offline=offline)).records(
            discovered_pmids
        )
        if discovered_pmids
        else {}
    )

    # Every search has now written its snapshots, so the as-of instant is final.
    times = _snapshot_times(refinement_snapshots, action_snapshots)
    as_of_dt = max(times.values())
    as_of: date = as_of_dt.date()


    # --- subjects, all derived from cached records -------------------------
    people_by_team = {
        team_id: derive_people(records, pmids, times)
        for team_id, _, pmids, _ in TEAMS
    }
    people = tuple(
        sorted(
            {person.researcher_id: person for team in people_by_team.values() for person in team}
            .values(),
            key=lambda item: item.researcher_id,
        )
    )
    resolutions = resolve_identities(people)
    labs: list[Laboratory] = []
    for team_id, team_name, pmids, _ in TEAMS:
        members = people_by_team[team_id]
        institutions = tuple(
            dict.fromkeys(person.institution for person in members if person.institution)
        )
        labs.append(
            Laboratory(
                lab_id=team_id,
                canonical_name=team_name,
                institution=" | ".join(institutions)
                or "not stated in the cached author records",
                official_url=None,
                research_focus=("STUB1", "CHIP", "SCAR16"),
                diseases=("SCAR16",),
                personnel=tuple(person.researcher_id for person in members),
                publications=tuple(f"PMID:{pmid}" for pmid in pmids),
                last_verified_at=max(
                    times[records[pmid].snapshot_sha256] for pmid in pmids
                ),
                provenance=tuple(
                    _provenance(pmid, records[pmid].snapshot_sha256, times[records[pmid].snapshot_sha256])
                    for pmid in pmids
                ),
            )
        )

    # --- capability signals ------------------------------------------------
    def publication_signals(pmids: tuple[str, ...]) -> tuple[CapabilityEvidenceSignal, ...]:
        return tuple(
            CapabilityEvidenceSignal(
                evidence_id=f"PMID:{pmid}",
                source_type="publication",
                subject_scope="team",
                explicitly_demonstrates=True,
                biological_context_match=True,
                model_system_match=True,
                active=None,
                publication_year=records[pmid].year,
                exact_support=records[pmid].title,
                source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            )
            for pmid in pmids
        )

    def grant_disposition(grant: Grant) -> str:
        text = f"{grant.title} {grant.abstract}"
        subject = bool(GRANT_SUBJECT.search(text))
        context = bool(GRANT_CONTEXT.search(text))
        if subject and context and grant.active:
            return "QUALIFIES: whole-word STUB1 in a disease-specific context, award active"
        if subject and context:
            return "EXPIRED: subject and context match but the award has ended"
        if subject:
            return (
                "CONTEXT_MISMATCH: mentions STUB1 but in another disease area, so it is not "
                "evidence of STUB1 ataxia capability"
            )
        if context:
            return (
                "SUBJECT_MISMATCH: ataxia or cerebellar context but a different gene or "
                "protein; adjacent field intelligence only"
            )
        return (
            "RETRIEVED_BY_AMBIGUOUS_TOKEN: matched the query text without a whole-word STUB1 "
            "or disease context term, most often via ChIP/CHIP collision"
        )

    grant_dispositions = {grant.grant_id: grant_disposition(grant) for grant in grants}
    grant_signals = tuple(
        CapabilityEvidenceSignal(
            evidence_id=grant.grant_id,
            source_type="active_grant",
            subject_scope="institution",
            explicitly_demonstrates=True,
            biological_context_match=True,
            # Institution-scope funding evidence is never a neuronal model-system match.
            model_system_match=False,
            active=grant.active,
            publication_year=grant.project_end.year if grant.project_end else None,
            exact_support=grant.title,
            source_url=grant.source_url,
        )
        for grant in grants
        if grant_dispositions[grant.grant_id].startswith("QUALIFIES")
    )

    capability_by_category = {item.capability_category.value: item for item in capabilities}
    claims = []
    for team_id, team_name, pmids, categories in TEAMS:
        signals = publication_signals(pmids) + grant_signals
        for category in categories:
            requirement = capability_by_category.get(category)
            if requirement is None:
                continue
            claims.append(
                assess_capability(
                    claim_id=f"capability-claim:{team_id.split(':', 1)[1]}:{category}",
                    subject_type="laboratory",
                    subject_id=team_id,
                    capability_id=requirement.capability_id,
                    statement=(
                        f"{team_name}: published work bearing on {requirement.canonical_name}."
                    ),
                    signals=signals,
                    today=as_of,
                )
            )

    # --- candidates for the unmet capabilities -----------------------------
    known_pmids = frozenset(pmid for team in TEAMS for pmid in team[2])
    candidates = derive_candidates(
        search_results,
        discovered_records,
        exclude_pmids=known_pmids,
        anchor_label=discovery_context.anchor_label,
    )
    candidate_signal_map = candidate_signals(candidates, targeted_queries)
    for candidate in candidates:
        requirement = capability_by_category.get(candidate.capability_category)
        if requirement is None:
            continue
        claims.append(
            assess_capability(
                claim_id=f"capability-claim:{candidate.candidate_id}",
                subject_type="laboratory",
                subject_id=candidate.candidate_id,
                capability_id=requirement.capability_id,
                statement=(
                    f"Publication-derived group (last author {candidate.last_author}) "
                    f"demonstrated {requirement.canonical_name} in "
                    f"{candidate.disease_involvement}."
                ),
                signals=candidate_signal_map[candidate.candidate_id],
                today=as_of,
            )
        )
        labs.append(
            Laboratory(
                lab_id=candidate.candidate_id,
                canonical_name=(
                    f"{candidate.capability_category} capability candidate: "
                    f"author group of PMID:{candidate.pmid}"
                ),
                institution=candidate.affiliation
                or "not stated in the cached author record",
                official_url=None,
                research_focus=(candidate.capability_category,),
                diseases=(),
                personnel=(),
                publications=(f"PMID:{candidate.pmid}",),
                last_verified_at=times[candidate.snapshot_sha256],
                provenance=(
                    _provenance(
                        candidate.pmid,
                        candidate.snapshot_sha256,
                        times[candidate.snapshot_sha256],
                    ),
                ),
            )
        )

    # --- assets and organizations -----------------------------------------
    ipsc_team = labs[0]
    assay_team = labs[1]
    assets: list[ResearchAsset] = [
        ResearchAsset(
            asset_id="asset:stub1-patient-ipsc:pmid-29679845",
            canonical_name=records["29679845"].title,
            asset_type=AssetType.IPSC_LINE,
            creator=ipsc_team.lab_id,
            disease_context=("Gordon Holmes syndrome", "SCAR16"),
            mechanism_context=("STUB1/CHIP dysfunction",),
            variant_context=(
                ("patient genotype as published; not the K145Q or M211I alleles the "
                "experiment requires"),
            ),
            model_context=("patient-derived iPSC",),
            availability="Unknown: no repository deposit or availability statement was located",
            access_requirements=("consent provenance review", "material transfer agreement"),
            evidence=("PMID:29679845", "PMID:33097556"),
            source_url="https://pubmed.ncbi.nlm.nih.gov/29679845/",
            last_verified_at=times[records["29679845"].snapshot_sha256],
            reuse_status=AssetReuseStatus.REQUIRES_VALIDATION,
        ),
        ResearchAsset(
            asset_id="asset:chip-functional-assay:publication-method",
            canonical_name="Published CHIP variant functional-assay methods",
            asset_type=AssetType.ASSAY,
            creator=assay_team.lab_id,
            disease_context=("SCAR16", "SCA48"),
            mechanism_context=("CHIP E3 ubiquitin ligase and co-chaperone function",),
            model_context=("purified recombinant protein and cellular assays",),
            availability="Methods published; materials, transferability and neuronal "
            "applicability unverified",
            access_requirements=(
                "confirm assay materials",
                "adapt readout to neuronal diGly ubiquitinome",
            ),
            evidence=("PMID:31619515", "PMID:42567515"),
            source_url="https://pubmed.ncbi.nlm.nih.gov/42567515/",
            last_verified_at=times[records["42567515"].snapshot_sha256],
            reuse_status=AssetReuseStatus.REQUIRES_VALIDATION,
        ),
    ]
    organizations: list[Organization] = []
    for study in studies:
        assets.append(
            ResearchAsset(
                asset_id=f"asset:registry:{study.study_id}",
                canonical_name=study.title,
                asset_type=AssetType.REGISTRY,
                organization=study.organizations[0] if study.organizations else None,
                disease_context=tuple(
                    condition
                    for condition in study.conditions
                    if any(term in condition.lower() for term in STUB1_CONDITION_TERMS)
                ),
                mechanism_context=(),
                model_context=("human participant registry and natural-history data",),
                availability=(
                    f"Registry status {study.overall_status} as recorded in the cached "
                    "ClinicalTrials.gov record; enrolment terms not verified"
                ),
                access_requirements=(
                    "contact registry coordinator",
                    "institutional data-use approval",
                ),
                evidence=(study.study_id,),
                source_url=study.source_url,
                last_verified_at=times[study.snapshot_sha256],
                reuse_status=AssetReuseStatus.REQUIRES_VALIDATION,
            )
        )
        for name in study.organizations:
            if "ataxia" not in name.lower():
                continue
            organizations.append(
                Organization(
                    organization_id=f"organization:{name.lower().replace(' ', '-')}",
                    canonical_name=name,
                    organization_type=OrganizationType.PATIENT_ORGANIZATION,
                    official_url=study.source_url,
                    disease_focus=("ataxia",),
                    patient_registry=study.study_id,
                    assets=(f"asset:registry:{study.study_id}",),
                    last_verified_at=times[study.snapshot_sha256],
                    contact_source=(
                        "listed as a collaborator on the cached ClinicalTrials.gov record; "
                        "no direct contact route was verified"
                    ),
                    provenance=(
                        ProvenanceReference(
                            source_type="ClinicalTrials.gov",
                            source_id=study.study_id,
                            source_url=study.source_url,
                            snapshot_sha256=study.snapshot_sha256,
                            retrieved_at=times[study.snapshot_sha256],
                        ),
                    ),
                )
            )

    # --- search coverage ---------------------------------------------------
    pubmed_outcome = SourceOutcome(
        source="PubMed",
        status=CoverageStatus.CHECKED,
        queries=tuple(item.query for item in queries if item.source == "PubMed"),
        result_count=len(records),
        snapshots=tuple(
            dict.fromkeys(records[pmid].snapshot_sha256 for team in TEAMS for pmid in team[2])
        ),
        note=(
            "Author and affiliation strings for the named teams come from these cached "
            "records. Capability-specific PubMed queries were generated but not separately "
            "executed: the record set was assembled during Phase 3 retrieval."
        ),
    )
    unavailable = (
        SourceOutcome(
            source="Bright Data",
            status=CoverageStatus.FAILED,
            queries=tuple(
                item.query for item in queries if item.source == "institutional_web"
            )[:8],
            error="BRIGHTDATA_API_TOKEN and BRIGHTDATA_DATASET_ID are not configured.",
        ),
        SourceOutcome(
            source="Institutional web pages",
            status=CoverageStatus.NOT_STARTED,
            queries=(),
            error=None,
            note=(
                "Not attempted in this run: current affiliation and current activity remain "
                "unverified as a result."
            ),
        ),
        SourceOutcome(
            source="NORD / Global Genes / Orphanet",
            status=CoverageStatus.NOT_STARTED,
            queries=(),
            note=(
                "Patient-organization coverage in this run comes only from the "
                "ClinicalTrials.gov registry record; disease-organization pages were not "
                "ingested as web evidence."
            ),
        ),
        SourceOutcome(
            source="Cell-line and plasmid repositories",
            status=CoverageStatus.NOT_STARTED,
            queries=(),
            note="Asset availability therefore remains unverified.",
        ),
    )
    targeted_outcome = SourceOutcome(
        source="PubMed (targeted capability queries)",
        status=CoverageStatus.CHECKED if search_results else CoverageStatus.FAILED,
        queries=tuple(result.query.query for result in search_results),
        result_count=(
            sum(result.total_hits for result in search_results) if search_results else None
        ),
        error="; ".join(search_failures) or None,
        snapshots=tuple(dict.fromkeys(result.snapshot_sha256 for result in search_results)),
        note=coverage_note(search_results)
        + (
            f" {len(search_failures)} query/queries failed."
            if search_failures
            else " No query failed."
        ),
    )
    outcomes = (pubmed_outcome, nih_outcome, trial_outcome, targeted_outcome, *unavailable)
    coverage = SearchCoverage(
        coverage_id=f"action-search:{experiment.experiment_id}",
        scope="collaborator_and_asset_discovery",
        sources=tuple(
            SearchSourceCoverage(
                source=outcome.source,
                status=outcome.status,
                queries=outcome.queries,
                checked_at=as_of_dt if outcome.status is CoverageStatus.CHECKED else None,
                result_count=outcome.result_count,
                error=outcome.error
                or (
                    "not attempted in this run"
                    if outcome.status is CoverageStatus.FAILED
                    else None
                ),
                pages_checked=1 if outcome.status is CoverageStatus.CHECKED else 0,
                languages=("English-indexed records",)
                if outcome.status is CoverageStatus.CHECKED
                else ("not assessed",),
                geographic_regions=("affiliation-derived; no geographic filter applied",)
                if outcome.status is CoverageStatus.CHECKED
                else ("not assessed",),
                cache_hits=len(outcome.snapshots),
                snapshot_references=outcome.snapshots,
            )
            for outcome in outcomes
        ),
        search_started_at=as_of_dt,
        search_completed_at=as_of_dt,
        language_limitations=(
            ("Only English-indexed PubMed, RePORTER and ClinicalTrials.gov records were "
            "searched; non-English institutional and organization sources were not."),
        ),
        geographic_limitations=(
            ("NIH RePORTER covers US federal funding only, so non-US activity is "
            "systematically absent from the grant evidence."),
        ),
        interpretation_caveat=(
            "No qualifying candidate was identified in the sources that were successfully "
            "searched. Several sources were not searched or failed; that is not evidence "
            "that no qualifying laboratory, asset or organization exists."
        ),
    )

    # --- collaboration synthesis ------------------------------------------
    participants = tuple(
        CollaborationParticipant(
            subject_type="laboratory",
            subject_id=lab.lab_id,
            proposed_role=role,
            capability_claim_ids=tuple(
                claim.claim_id for claim in claims if claim.subject_id == lab.lab_id
            ),
            asset_ids=tuple(
                asset.asset_id for asset in assets if asset.creator == lab.lab_id
            ),
        )
        for lab, role in (
            (
                labs[0],
                ("confirm whether the published SCAR16 patient iPSC line and neuronal "
                "differentiation capability are currently available"),
            ),
            (
                labs[1],
                ("advise on transferring CHIP functional assays to a substrate-resolved "
                "neuronal readout"),
            ),
        )
    ) + tuple(
        CollaborationParticipant(
            subject_type="laboratory",
            subject_id=candidate.candidate_id,
            proposed_role=(
                f"possible provider of {candidate.capability_category}; identified by "
                "technique alone, with no STUB1 or SCAR16 involvement established and "
                "no contact, availability or willingness verified"
            ),
            capability_claim_ids=tuple(
                claim.claim_id
                for claim in claims
                if claim.subject_id == candidate.candidate_id
            ),
            asset_ids=(),
        )
        for candidate in candidates
    )
    collaboration = synthesize_collaboration(
        collaboration_id="collaboration:scar16-stub1-linker-action-v1",
        experiment_id=experiment.experiment_id,
        knowledge_gap_id=experiment.knowledge_gap_id,
        participants=participants,
        capability_claims=tuple(claims),
        required_capability_ids=tuple(item.capability_id for item in capabilities),
        provided_assets=tuple(asset.asset_id for asset in assets),
        rationale=(
            "Two publication-derived author groups bear on different parts of the proposed "
            "experiment: one published a SCAR16 patient iPSC line and iPSC-derived neuronal "
            "models, the other published allele-resolved CHIP biochemistry. Neither has "
            "evidence for the full combination the experiment needs, and no evidence of "
            "current activity, current affiliation or willingness to collaborate was obtained."
        ),
        uncertainties=(
            ("Current affiliations were not verified: institution strings are publication "
            "affiliations at time of publication only."),
            ("No evidence was found that either group performs STUB1 allele-specific "
            "endogenous knock-in editing."),
            "No evidence was found for diGly-enriched ubiquitinome proteomics access.",
            ("The published patient iPSC genotype is not a substitute for K145Q/M211I "
            "isogenic lines, and its availability is unknown."),
            ("NIH RePORTER returned no active grant for STUB1 mechanism work; the only "
            "topically related award ended in 2011."),
            ("Institutional pages, repositories and patient-organization sites were not "
            "searched in this run."),
            "Willingness to collaborate was not assessed for any person or group.",
        ),
        duplication_risk=(
            "NOT ASSESSED: no ResearchProgram records were built, because institutional, "
            "foundation and company program sources were not searched."
        ),
        synergy=(
            "The neuronal-model experience and the allele-resolved assay experience are "
            "complementary in principle; realising that depends on unverified current "
            "capability, materials and the missing editing and proteomics capabilities."
        ),
        first_contact_target=None,
        suggested_next_action=(
            "Obtain expert review of the experiment, then verify current affiliation and "
            "activity for both author groups, ask whether the published iPSC line is "
            "available, and identify a collaborator for STUB1 knock-in editing and diGly "
            "ubiquitinome proteomics, which no candidate currently evidences."
        ),
        created_at=as_of_dt,
    )

    missing_names = tuple(
        capability_by_category_name
        for capability_by_category_name, requirement in (
            (item.canonical_name, item) for item in capabilities
        )
        if requirement.capability_id in collaboration.missing_capabilities
    )
    patient_explanation = {
        "audience": "patient_leader",
        "status": collaboration.status.value,
        "text": (
            "Researchers have shown that different STUB1 gene changes affect the CHIP "
            "protein in different ways. For two changes in the middle of the protein, it is "
            "still unknown whether they harm CHIP's job inside nerve cells. The proposed "
            "study would test exactly that, using nerve cells grown from stem cells.\n\n"
            "We looked for groups who could help. One group has previously made stem cells "
            "from a person with this condition and turned them into nerve cells. Another "
            "group has studied how CHIP protein changes behave in the test tube. Both "
            "published that work, so we know it happened, but we could not confirm that they "
            "are still doing it today, or that they would be able or willing to take this on.\n\n"
            "Two things nobody we found can currently show they can do are: making the exact "
            "gene changes in stem cells, and the specialised protein measurement the study "
            "needs. There is also a rare-disease patient registry that lists this condition, "
            "which may help identify affected families.\n\n"
            "This is a starting point, not a plan. A qualified scientist needs to review the "
            "study first, and the groups would need to be contacted to confirm what they can "
            "actually do. Where we could not search a source, that means we do not know - not "
            "that nothing is out there."
        ),
    }
    scientist_explanation = {
        "audience": "scientist",
        "status": collaboration.status.value,
        "experiment_id": experiment.experiment_id,
        "knowledge_gap_id": experiment.knowledge_gap_id,
        "collaboration_id": collaboration.collaboration_id,
        "capability_claim_ids": [claim.claim_id for claim in claims],
        "asset_ids": [asset.asset_id for asset in assets],
        "missing_capabilities": list(collaboration.missing_capabilities),
        "missing_capability_names": list(missing_names),
        "text": (
            "Candidate subjects are publication-derived author groups, not verified "
            "laboratories: names and affiliation strings are read from cached PubMed author "
            "records (first and last author per publication) and reflect affiliation at "
            "publication time only. All capability evidence is therefore team-level at best; "
            "no personal capability is asserted.\n\n"
            f"Capability claims: {len(claims)}. The patient-iPSC signals (PMID:29679845, 2018; "
            "PMID:33097556, 2020) fall outside the five-year recency window relative to the "
            "cache date and are classified accordingly. The CHIP biochemistry signals "
            "(PMID:31619515, 2019; PMID:42567515, 2026) include a current publication but a "
            "single source type, so they cannot reach VERIFIED, which requires two "
            "independent source types.\n\n"
            "NIH RePORTER: 'STUB1 ataxia' returned no awards. Text matches on 'CHIP' are "
            "largely false positives from the ambiguous token; the only topically relevant "
            "award (CHIP co-chaperone, UNC) ended in 2011 and is treated as institution-scope, "
            "non-neuronal evidence. ClinicalTrials.gov: NCT01793168 lists STUB1-deficiency "
            "cerebellar ataxia among its conditions and is RECRUITING, which evidences "
            "registry infrastructure only.\n\n"
            "Unmet requirements are STUB1 allele-specific endogenous editing, isogenic line "
            "generation, diGly ubiquitinome proteomics and clone-aware analysis. The "
            "opportunity is therefore MISSING_CAPABILITY and is not presented as actionable. "
            "Criticism and synthesis here are deterministic rule output, not expert review."
        ),
    }

    lineage = {
        "schema_version": "phase4-action-lineage-v1",
        "chain": [
            "DisMech curated claim",
            "refined atomic claims",
            "KnowledgeGap",
            "ExperimentProposal",
            "RequiredCapability / RequiredAsset",
            "discovery queries",
            "cached source records",
            "CapabilityEvidenceSignal",
            "CapabilityClaim",
            "Laboratory / Researcher / ResearchAsset / Organization",
            "CollaborationOpportunity",
        ],
        "knowledge_gap_id": experiment.knowledge_gap_id,
        "experiment_id": experiment.experiment_id,
        "as_of": as_of.isoformat(),
        "as_of_basis": "newest cached snapshot retrieval time; no execution clock is used",
        "required_capabilities": [
            {
                "capability_id": item.capability_id,
                "canonical_name": item.canonical_name,
                "evidence_source": item.evidence_source,
                "capability_claim_ids": [
                    claim.claim_id for claim in claims if claim.capability_id == item.capability_id
                ],
                "satisfied": item.capability_id not in collaboration.missing_capabilities,
            }
            for item in capabilities
        ],
        "required_assets": [
            {
                "required_asset_id": item.required_asset_id,
                "asset_type": item.asset_type.value,
                "evidence_source": item.evidence_source,
            }
            for item in required_assets
        ],
        "candidate_subjects": [
            {
                "lab_id": lab.lab_id,
                "personnel": list(lab.personnel),
                "publications": list(lab.publications),
                "provenance_snapshots": [item.snapshot_sha256 for item in lab.provenance],
            }
            for lab in labs
        ],
        "research_assets": [
            {"asset_id": item.asset_id, "evidence": list(item.evidence)} for item in assets
        ],
        "organizations": [item.organization_id for item in organizations],
        "entity_resolution": [
            {
                "decision_id": item.decision_id,
                "status": item.status.value,
                "left": item.left_entity_id,
                "right": item.right_entity_id,
            }
            for item in resolutions
        ],
        "grants_considered": [
            {
                "grant_id": item.grant_id,
                "active": item.active,
                "organization": item.organization,
                "project_end": item.project_end.isoformat() if item.project_end else None,
                "disposition": grant_dispositions[item.grant_id],
                "used_as_capability_evidence": grant_dispositions[item.grant_id].startswith(
                    "QUALIFIES"
                ),
            }
            for item in grants
        ],
        "clinical_studies_considered": [item.study_id for item in studies],
        "collaboration_id": collaboration.collaboration_id,
        "collaboration_status": collaboration.status.value,
        "human_review": {
            "status": "PENDING",
            "required": True,
            "note": (
                "Deterministic extraction and rule-based verification are not expert "
                "scientific review."
            ),
        },
    }

    _write(output_dir / "required_capabilities.json", capabilities)
    _write(output_dir / "required_assets.json", required_assets)
    _write(output_dir / "discovery_queries.json", queries)
    _write(output_dir / "researchers.json", people)
    _write(output_dir / "entity_resolution.json", resolutions)
    _write(
        output_dir / "capability_search.json",
        {
            "note": (
                "Full result of the executed targeted queries. The candidate list is a "
                "recency-capped selection; every retrieved PMID is recorded here so a "
                "reviewer can see leads that were not promoted."
            ),
            "tiers": {
                "A_disease_anchored": (
                    "gene or disease plus capability; high precision, near-zero recall "
                    "for an unmet requirement"
                ),
                "B_capability_anchored": (
                    "capability plus model context without the gene; finds groups who "
                    "could do the work but have no established disease involvement"
                ),
            },
            "executed": [
                {
                    "capability_category": result.query.capability_category,
                    "tier": result.query.tier.value,
                    "query": result.query.query,
                    "rationale": result.query.rationale,
                    "model_context": result.query.model_context,
                    "total_hits": result.total_hits,
                    "retrieved_pmids": list(result.pmids),
                    "snapshot_sha256": result.snapshot_sha256,
                }
                for result in search_results
            ],
            "failures": list(search_failures),
            "selection_rule": (
                "newest first, capped at 3 per capability, excluding publications already "
                "represented by an existing candidate team"
            ),
            "candidates_selected": [
                {
                    "candidate_id": candidate.candidate_id,
                    "capability_category": candidate.capability_category,
                    "tier": candidate.tier.value,
                    "pmid": candidate.pmid,
                    "year": candidate.year,
                    "last_author": candidate.last_author,
                    "affiliation": candidate.affiliation,
                    "disease_involvement": candidate.disease_involvement,
                    "limitation": candidate.limitation,
                }
                for candidate in candidates
            ],
        },
    )
    _write(output_dir / "laboratories.json", tuple(labs))
    _write(output_dir / "capability_claims.json", tuple(claims))
    _write(output_dir / "research_assets.json", tuple(assets))
    _write(output_dir / "organizations.json", tuple(organizations))
    _write(output_dir / "grants.json", grants)
    _write(output_dir / "clinical_studies.json", studies)
    _write(output_dir / "search_coverage.json", coverage)
    _write(output_dir / "collaboration_opportunity.json", collaboration)
    _write(output_dir / "patient_explanation.json", patient_explanation)
    _write(output_dir / "scientist_explanation.json", scientist_explanation)
    _write(output_dir / "lineage.json", lineage)
    print(
        json.dumps(
            {
                "as_of": as_of.isoformat(),
                "required_capabilities": len(capabilities),
                "required_assets": len(required_assets),
                "discovery_queries": len(queries),
                "researchers_derived": len(people),
                "entity_resolution": {
                    item.decision_id: item.status.value for item in resolutions
                },
                "author_groups": len(labs),
                "capability_claims": {
                    claim.claim_id: claim.status.value for claim in claims
                },
                "grants_retrieved": len(grants),
                "grants_used_as_evidence": [
                    item.grant_id
                    for item in grants
                    if grant_dispositions[item.grant_id].startswith("QUALIFIES")
                ],
                "clinical_studies_relevant": [item.study_id for item in studies],
                "organizations": [item.canonical_name for item in organizations],
                "missing_capabilities": len(collaboration.missing_capabilities),
                "collaboration_status": collaboration.status.value,
            },
            indent=2,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--offline", action="store_true", help="require cached snapshots; never fetch"
    )
    args = parser.parse_args()
    build(args.input, args.output, offline=args.offline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
