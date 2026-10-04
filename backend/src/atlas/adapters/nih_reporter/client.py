"""Read-only NIH RePORTER v2 search with immutable response snapshots."""

from __future__ import annotations

from datetime import date
from typing import Any

from atlas.adapters.literature.client import RetrievalError, SnapshotFetcher, fetch_json
from atlas.domain.discovery import Grant

NIH_REPORTER_SEARCH = "https://api.reporter.nih.gov/v2/projects/search"


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


class NIHReporterClient:
    def __init__(self, fetcher: SnapshotFetcher, *, endpoint: str = NIH_REPORTER_SEARCH) -> None:
        self.fetcher = fetcher
        self.endpoint = endpoint

    def search(
        self,
        query: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, tuple[Grant, ...], str]:
        payload: dict[str, Any] = {
            "criteria": {
                "advanced_text_search": {
                    "operator": "and",
                    "search_field": "all",
                    "search_text": query,
                }
            },
            "include_fields": [
                "ProjectNum",
                "ProjectTitle",
                "PrincipalInvestigators",
                "Organization",
                "AbstractText",
                "ProjectStartDate",
                "ProjectEndDate",
            ],
            "offset": offset,
            "limit": limit,
            "sort_field": "project_start_date",
            "sort_order": "desc",
        }
        raw, snapshot_hash = fetch_json(self.fetcher, self.endpoint, post_json=payload)
        if not isinstance(raw, dict):
            raise RetrievalError("malformed NIH RePORTER response")
        meta = raw.get("meta", {})
        results = raw.get("results", [])
        if not isinstance(results, list):
            raise RetrievalError("malformed NIH RePORTER results")
        today = date.today()
        grants = []
        for item in results:
            if not isinstance(item, dict):
                continue
            end = _parse_date(item.get("project_end_date"))
            organization = item.get("organization") or {}
            investigators = item.get("principal_investigators") or []
            grant_id = str(item.get("project_num") or "")
            if not grant_id:
                continue
            organization_name = (
                organization.get("org_name")
                if isinstance(organization, dict)
                else organization
            )
            grants.append(
                Grant(
                    grant_id=grant_id,
                    title=str(item.get("project_title") or ""),
                    principal_investigators=tuple(
                        str(person.get("full_name") or "")
                        for person in investigators
                        if isinstance(person, dict) and person.get("full_name")
                    ),
                    organization=str(organization_name or ""),
                    abstract=str(item.get("abstract_text") or ""),
                    project_start=_parse_date(item.get("project_start_date")),
                    project_end=end,
                    active=end is not None and end >= today,
                    source_url=f"https://reporter.nih.gov/project-details/{grant_id}",
                    snapshot_sha256=snapshot_hash,
                )
            )
        total = int(meta.get("total", len(grants))) if isinstance(meta, dict) else len(grants)
        return total, tuple(grants), snapshot_hash
