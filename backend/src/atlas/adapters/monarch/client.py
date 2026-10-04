"""Small Monarch v3 HTTP adapter; API response payloads remain source snapshots."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class MonarchRequestError(RuntimeError):
    """A visible retrieval failure; callers must record it in search coverage."""


class MonarchClient:
    def __init__(
        self,
        base_url: str = "https://api.monarchinitiative.org/v3/api",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def entity_url(self, entity_id: str) -> str:
        return f"{self.base_url}/entity/{quote(entity_id, safe=':')}"

    def pathograph_url(self, node_id: str) -> str:
        return f"{self.base_url}/pathograph/{quote(node_id, safe=':')}"

    def search_url(self, query: str, *, category: str | None = None, limit: int = 20) -> str:
        if not 0 <= limit <= 500:
            raise ValueError("Monarch API limit must be between 0 and 500")
        parameters: dict[str, Any] = {"q": query, "limit": limit}
        if category:
            parameters["category"] = category
        return f"{self.base_url}/search?{urlencode(parameters)}"

    def association_url(
        self,
        *,
        entity: str,
        category: str | None = None,
        direct: bool = False,
        limit: int = 100,
    ) -> str:
        if not 0 <= limit <= 500:
            raise ValueError("Monarch API limit must be between 0 and 500")
        params: list[tuple[str, str | int]] = [
            ("entity", entity),
            ("direct", str(direct).lower()),
            ("limit", limit),
        ]
        if category:
            params.append(("category", category))
        return f"{self.base_url}/association?{urlencode(params)}"

    def get_json(self, url: str) -> dict[str, Any]:
        """Fetch JSON or raise a visible failure; never convert failure to empty data."""
        import json

        request = Request(url, headers={"Accept": "application/json", "User-Agent": "atlas/0.1"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                payload = json.loads(response.read())
        except Exception as exc:  # network failure types vary by Python/platform
            raise MonarchRequestError(f"Monarch retrieval failed for {url}: {exc}") from exc
        if not isinstance(payload, dict):
            raise MonarchRequestError(f"Monarch returned a non-object payload for {url}")
        return payload

