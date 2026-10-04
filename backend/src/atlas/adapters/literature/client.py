"""Read-only literature/registry adapters with snapshot caching.

Every response body is written to a cache directory keyed by the SHA-256 of the
request, together with its URL, retrieval time and content hash, so a refinement
run can be replayed byte-for-byte. Failures raise ``RetrievalError``; callers
must record them as ``FAILED`` search coverage, never as empty results.
"""

from __future__ import annotations

import html
import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EUROPE_PMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"


class RetrievalError(RuntimeError):
    """A visible retrieval failure."""


@dataclass(frozen=True, slots=True)
class CachedResponse:
    url: str
    body: bytes
    sha256: str
    retrieved_at: datetime
    from_cache: bool


class SnapshotFetcher:
    """HTTP GET/POST with an on-disk, content-hashed snapshot cache."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        offline: bool = False,
        timeout_seconds: float = 30.0,
        min_interval_seconds: float = 0.35,
    ) -> None:
        self.cache_dir = cache_dir
        self.offline = offline
        self.timeout_seconds = timeout_seconds
        self.min_interval_seconds = min_interval_seconds
        self._last_request = 0.0
        cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch(
        self,
        url: str,
        *,
        post_json: dict[str, Any] | list[dict[str, Any]] | None = None,
        request_headers: dict[str, str] | None = None,
        force_refresh: bool = False,
    ) -> CachedResponse:
        key_material = url if post_json is None else url + json.dumps(post_json, sort_keys=True)
        key = sha256(key_material.encode()).hexdigest()
        body_path = self.cache_dir / f"{key}.body"
        meta_path = self.cache_dir / f"{key}.json"
        if body_path.exists() and meta_path.exists() and not force_refresh:
            meta = json.loads(meta_path.read_text())
            body = body_path.read_bytes()
            return CachedResponse(
                url=url,
                body=body,
                sha256=sha256(body).hexdigest(),
                retrieved_at=datetime.fromisoformat(meta["retrieved_at"]),
                from_cache=True,
            )
        if self.offline:
            raise RetrievalError(f"offline mode and no cached snapshot for {url}")
        wait = self.min_interval_seconds - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        data = None
        headers = {"User-Agent": "atlas-refinement/0.1 (research; contact via repository)"}
        if request_headers:
            headers.update(request_headers)
        if post_json is not None:
            data = json.dumps(post_json).encode()
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                body = response.read()
        except Exception as exc:  # network failure types vary by platform
            raise RetrievalError(f"retrieval failed for {url}: {exc}") from exc
        finally:
            self._last_request = time.monotonic()
        retrieved_at = datetime.now(UTC)
        body_path.write_bytes(body)
        meta_path.write_text(
            json.dumps(
                {
                    "url": url,
                    "post_json": post_json,
                    "retrieved_at": retrieved_at.isoformat(),
                    "sha256": sha256(body).hexdigest(),
                },
                indent=2,
            )
        )
        return CachedResponse(
            url=url,
            body=body,
            sha256=sha256(body).hexdigest(),
            retrieved_at=retrieved_at,
            from_cache=False,
        )


@dataclass(frozen=True, slots=True)
class PubMedAuthor:
    name: str
    affiliations: tuple[str, ...]


_CONTACT_IN_AFFILIATION = re.compile(
    r"\s*(electronic address|e-?mail)\s*:.*$", re.IGNORECASE | re.DOTALL
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def clean_affiliation(value: str) -> str:
    """Strip incidental contact details from a PubMed affiliation string.

    Affiliations routinely carry a corresponding author's email. That is personal
    contact data with no place in a generated artifact, so it is removed here at
    the adapter boundary rather than at each call site.
    """
    without_contact = _CONTACT_IN_AFFILIATION.sub("", value)
    return _EMAIL.sub("[email removed]", without_contact).strip().rstrip(";").strip()


@dataclass(frozen=True, slots=True)
class PubMedRecord:
    pmid: str
    title: str
    abstract: str
    journal: str | None
    year: int | None
    publication_types: tuple[str, ...]
    snapshot_sha256: str
    authors: tuple[PubMedAuthor, ...] = ()


def _element_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


class PubMedClient:
    def __init__(self, fetcher: SnapshotFetcher) -> None:
        self.fetcher = fetcher

    def search(self, term: str, *, retmax: int = 50) -> tuple[int, tuple[str, ...], str]:
        url = f"{EUTILS}/esearch.fcgi?" + urlencode(
            {"db": "pubmed", "term": term, "retmode": "json", "retmax": retmax, "sort": "relevance"}
        )
        response = self.fetcher.fetch(url)
        try:
            result = json.loads(response.body)["esearchresult"]
            return int(result["count"]), tuple(result.get("idlist", ())), response.sha256
        except (KeyError, ValueError) as exc:
            raise RetrievalError(f"malformed PubMed esearch response for {term!r}") from exc

    def records(self, pmids: tuple[str, ...]) -> dict[str, PubMedRecord]:
        if not pmids:
            return {}
        url = f"{EUTILS}/efetch.fcgi?" + urlencode(
            {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}
        )
        response = self.fetcher.fetch(url)
        try:
            root = ET.fromstring(response.body)
        except ET.ParseError as exc:
            raise RetrievalError("malformed PubMed efetch XML") from exc
        result: dict[str, PubMedRecord] = {}
        for article in root.iter("PubmedArticle"):
            pmid = _element_text(article.find(".//MedlineCitation/PMID"))
            abstract_parts = []
            for part in article.findall(".//Abstract/AbstractText"):
                label = part.get("Label")
                text = _element_text(part)
                abstract_parts.append(f"{label}: {text}" if label else text)
            year_text = _element_text(article.find(".//JournalIssue/PubDate/Year")) or (
                _element_text(article.find(".//JournalIssue/PubDate/MedlineDate"))[:4]
            )
            authors = []
            for author in article.findall(".//AuthorList/Author"):
                collective = _element_text(author.find("CollectiveName"))
                family = _element_text(author.find("LastName"))
                given = _element_text(author.find("ForeName"))
                name = collective or " ".join(item for item in (given, family) if item)
                if name:
                    authors.append(
                        PubMedAuthor(
                            name=name,
                            affiliations=tuple(
                                _element_text(item)
                                for item in author.findall(".//AffiliationInfo/Affiliation")
                                if _element_text(item)
                            ),
                        )
                    )
            result[pmid] = PubMedRecord(
                pmid=pmid,
                title=_element_text(article.find(".//ArticleTitle")),
                abstract="\n".join(abstract_parts),
                journal=_element_text(article.find(".//Journal/Title")) or None,
                year=int(year_text) if year_text.isdigit() else None,
                publication_types=tuple(
                    _element_text(item) for item in article.findall(".//PublicationType")
                ),
                snapshot_sha256=response.sha256,
                authors=tuple(authors),
            )
        return result


class EuropePMCClient:
    def __init__(self, fetcher: SnapshotFetcher) -> None:
        self.fetcher = fetcher

    def pmcid_for(self, pmid: str) -> str | None:
        url = f"{EUROPE_PMC}/search?" + urlencode(
            {"query": f"EXT_ID:{pmid} AND SRC:MED", "resultType": "lite", "format": "json"}
        )
        payload = json.loads(self.fetcher.fetch(url).body)
        results = payload.get("resultList", {}).get("result", [])
        if not results:
            return None
        pmcid = results[0].get("pmcid")
        open_access = results[0].get("isOpenAccess") == "Y"
        return str(pmcid) if pmcid and open_access else None

    def full_text(self, pmcid: str) -> tuple[str, str] | None:
        """Plain text of an open-access article and the snapshot hash, if available."""
        url = f"{EUROPE_PMC}/{pmcid}/fullTextXML"
        try:
            response = self.fetcher.fetch(url)
        except RetrievalError:
            return None
        text = re.sub(r"<[^>]+>", " ", response.body.decode("utf-8", errors="replace"))
        return html.unescape(re.sub(r"\s+", " ", text)), response.sha256

    def search(self, query: str, *, page_size: int = 25) -> tuple[int, list[dict[str, Any]], str]:
        url = f"{EUROPE_PMC}/search?" + urlencode(
            {"query": query, "resultType": "lite", "format": "json", "pageSize": page_size}
        )
        response = self.fetcher.fetch(url)
        payload = json.loads(response.body)
        return (
            int(payload.get("hitCount", 0)),
            list(payload.get("resultList", {}).get("result", [])),
            response.sha256,
        )


def fetch_json(fetcher: SnapshotFetcher, url: str, **kwargs: Any) -> tuple[Any, str]:
    response = fetcher.fetch(url, **kwargs)
    try:
        return json.loads(response.body), response.sha256
    except ValueError as exc:
        raise RetrievalError(f"non-JSON response from {url}") from exc
