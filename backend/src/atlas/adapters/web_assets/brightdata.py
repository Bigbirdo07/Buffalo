"""Bright Data discovery adapter that emits unverified evidence candidates only.

The adapter supports the Web Scraper API trigger/snapshot flow. Dataset-specific
input records are supplied by the caller because Bright Data datasets have
different schemas. API tokens are request headers and are never written to the
snapshot metadata.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import urlencode, urlparse

from atlas.adapters.literature.client import RetrievalError, SnapshotFetcher
from atlas.domain.discovery import (
    BrightDataUsage,
    ExtractionStatus,
    SourceQuality,
    WebEvidenceCandidate,
)

BRIGHT_DATA_API = "https://api.brightdata.com/datasets/v3"


class BrightDataAdapter:
    def __init__(
        self,
        fetcher: SnapshotFetcher,
        *,
        api_token: str,
        dataset_id: str,
        api_base: str = BRIGHT_DATA_API,
    ) -> None:
        if not api_token:
            raise ValueError("Bright Data API token is required")
        if not dataset_id:
            raise ValueError("Bright Data dataset ID is required")
        self.fetcher = fetcher
        self.api_token = api_token
        self.dataset_id = dataset_id
        self.api_base = api_base.rstrip("/")

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}"}

    def trigger(
        self,
        inputs: list[dict[str, object]],
        *,
        force_refresh: bool = False,
    ) -> tuple[str, str, bool]:
        url = f"{self.api_base}/trigger?" + urlencode(
            {"dataset_id": self.dataset_id, "include_errors": "true"}
        )
        response = self.fetcher.fetch(
            url,
            post_json=inputs,
            request_headers=self._headers,
            force_refresh=force_refresh,
        )
        try:
            payload = json.loads(response.body)
            snapshot_id = str(payload["snapshot_id"])
        except (ValueError, KeyError, TypeError) as exc:
            raise RetrievalError("malformed Bright Data trigger response") from exc
        return snapshot_id, response.sha256, response.from_cache

    def retrieve(
        self,
        snapshot_id: str,
        *,
        force_refresh: bool = False,
    ) -> tuple[list[dict[str, object]], str, datetime, bool]:
        url = f"{self.api_base}/snapshot/{snapshot_id}?format=json"
        response = self.fetcher.fetch(
            url,
            request_headers=self._headers,
            force_refresh=force_refresh,
        )
        try:
            payload = json.loads(response.body)
        except ValueError as exc:
            raise RetrievalError("Bright Data snapshot is not ready or is malformed") from exc
        if isinstance(payload, dict):
            records: object = payload.get("data", payload.get("results", []))
        else:
            records = payload
        if not isinstance(records, list):
            raise RetrievalError("Bright Data snapshot did not contain a record list")
        typed_records = [item for item in records if isinstance(item, dict)]
        return typed_records, response.sha256, response.retrieved_at, response.from_cache

    def evidence_candidates(
        self,
        snapshot_id: str,
        *,
        discovery_query: str,
        source_type: str,
        source_quality: SourceQuality,
        force_refresh: bool = False,
    ) -> tuple[tuple[WebEvidenceCandidate, ...], BrightDataUsage]:
        records, snapshot_hash, retrieved_at, cached = self.retrieve(
            snapshot_id,
            force_refresh=force_refresh,
        )
        candidates = []
        for record in records:
            url = str(record.get("url") or record.get("link") or "")
            raw_text = str(
                record.get("raw_text")
                or record.get("text")
                or record.get("content")
                or ""
            )
            if not url or not raw_text:
                continue
            raw_passages = record.get("relevant_passages")
            if isinstance(raw_passages, list):
                passages = tuple(str(item) for item in raw_passages if str(item).strip())
            else:
                description = str(record.get("description") or "").strip()
                passages = (description,) if description else ()
            candidates.append(
                WebEvidenceCandidate(
                    url=url,
                    title=str(record.get("title") or url),
                    domain=urlparse(url).netloc.lower(),
                    retrieved_at=retrieved_at,
                    source_type=source_type,
                    organization=(
                        str(record["organization"]) if record.get("organization") else None
                    ),
                    person=str(record["person"]) if record.get("person") else None,
                    raw_text=raw_text,
                    relevant_passages=passages,
                    discovery_query=discovery_query,
                    extraction_status=ExtractionStatus.EXTRACTED,
                    source_quality=source_quality,
                    content_hash=sha256(raw_text.encode()).hexdigest(),
                    snapshot_reference=snapshot_hash,
                )
            )
        usage = BrightDataUsage(
            query=discovery_query,
            dataset=self.dataset_id,
            endpoint=f"{self.api_base}/snapshot/{snapshot_id}",
            pages_fetched=len(records),
            estimated_credits=None,
            estimated_cost=None,
            cached=cached,
            snapshot_reference=snapshot_hash,
            retrieved_at=datetime.now(UTC),
        )
        return tuple(candidates), usage
