"""Read-only ClinicalTrials.gov API v2 client."""

from __future__ import annotations

from urllib.parse import urlencode

from atlas.adapters.literature.client import RetrievalError, SnapshotFetcher, fetch_json
from atlas.domain.discovery import ClinicalStudy

CLINICAL_TRIALS_STUDIES = "https://clinicaltrials.gov/api/v2/studies"


def _names(items: object, key: str) -> tuple[str, ...]:
    if not isinstance(items, list):
        return ()
    return tuple(
        str(item[key])
        for item in items
        if isinstance(item, dict) and isinstance(item.get(key), str)
    )


class ClinicalTrialsClient:
    def __init__(
        self,
        fetcher: SnapshotFetcher,
        *,
        endpoint: str = CLINICAL_TRIALS_STUDIES,
    ) -> None:
        self.fetcher = fetcher
        self.endpoint = endpoint

    def search(
        self,
        query: str,
        *,
        page_size: int = 50,
    ) -> tuple[int, tuple[ClinicalStudy, ...], str]:
        url = f"{self.endpoint}?" + urlencode(
            {"query.term": query, "pageSize": page_size, "format": "json"}
        )
        raw, snapshot_hash = fetch_json(self.fetcher, url)
        if not isinstance(raw, dict) or not isinstance(raw.get("studies", []), list):
            raise RetrievalError("malformed ClinicalTrials.gov response")
        studies = []
        for raw_study in raw.get("studies", []):
            if not isinstance(raw_study, dict):
                continue
            protocol = raw_study.get("protocolSection", {})
            if not isinstance(protocol, dict):
                continue
            identification = protocol.get("identificationModule", {})
            status = protocol.get("statusModule", {})
            contacts = protocol.get("contactsLocationsModule", {})
            conditions = protocol.get("conditionsModule", {})
            arms = protocol.get("armsInterventionsModule", {})
            sponsor = protocol.get("sponsorCollaboratorsModule", {})
            if not all(
                isinstance(item, dict)
                for item in (identification, status, contacts, conditions, arms, sponsor)
            ):
                continue
            nct_id = str(identification.get("nctId") or "")
            if not nct_id:
                continue
            investigators = _names(contacts.get("overallOfficials"), "name")
            organizations = _names(sponsor.get("collaborators"), "name")
            lead = sponsor.get("leadSponsor")
            if isinstance(lead, dict) and lead.get("name"):
                organizations = (str(lead["name"]), *organizations)
            locations = _names(contacts.get("locations"), "facility")
            studies.append(
                ClinicalStudy(
                    study_id=nct_id,
                    title=str(identification.get("briefTitle") or ""),
                    overall_status=str(status.get("overallStatus") or "UNKNOWN"),
                    investigators=investigators,
                    organizations=organizations,
                    locations=locations,
                    conditions=tuple(str(item) for item in conditions.get("conditions", [])),
                    interventions=_names(arms.get("interventions"), "name"),
                    source_url=f"https://clinicaltrials.gov/study/{nct_id}",
                    snapshot_sha256=snapshot_hash,
                )
            )
        total = int(raw.get("totalCount", len(studies)))
        return total, tuple(studies), snapshot_hash
