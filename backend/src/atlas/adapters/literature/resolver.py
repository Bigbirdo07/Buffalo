"""Resolve upstream reference forms to a canonical identifier.

DisMech references one publication in several forms. Measured over all 3,289
entries, 22,052 of 226,106 evidence items (9.8%) are not plain PMIDs: ORPHA
7,408, DOI 5,677, bare URL 5,349, clinicaltrials 1,819, CGGV 1,391, and a tail of
GEO/PPR/ICTRP/NCIT/CIViC/CGDS/STRCHIVE.

Two consequences this module addresses:

1. **Checkability.** A reference that cannot be resolved can never be verified,
   so its evidence is inert. PMC URLs and DOIs are mechanically resolvable.
2. **Identity.** The same paper cited two ways does not deduplicate, so
   independence counting can treat one study as two. In the SCAR20 entry,
   ``pathophysiology[1]`` cites both ``PMID:29635513`` and
   ``url:https://pmc.ncbi.nlm.nih.gov/articles/PMC5961352/``, which are the same
   paper; 185 objects corpus-wide cite both a PMID and a PMC URL in one evidence
   list. Rule A4 requires two *independent* publications to contradict a claim,
   so this is a correctness problem, not untidiness.

Every lookup goes through the snapshot cache, so resolution is replayable
offline. A form with no resolver returns None and stays honestly unresolvable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlencode

from atlas.adapters.literature.client import RetrievalError, SnapshotFetcher, fetch_json

ID_CONVERTER = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
EUROPE_PMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

_PMID = re.compile(r"^PMID:\s*(\d+)$", re.IGNORECASE)
_PMCID = re.compile(r"PMC(\d+)", re.IGNORECASE)
_DOI_PREFIX = re.compile(r"^DOI:\s*", re.IGNORECASE)
_BARE_DOI = re.compile(r"^10\.\d{4,9}/\S+$")


@dataclass(frozen=True, slots=True)
class Resolution:
    """One reference form mapped, or not, to a canonical identifier."""

    upstream_form: str
    canonical: str | None
    method: str
    note: str

    @property
    def resolved(self) -> bool:
        return self.canonical is not None


def _pmid(value: str) -> str:
    return f"PMID:{value}"


def resolve_reference(
    reference: str, fetcher: SnapshotFetcher | None = None
) -> Resolution:
    """Map an upstream reference string to ``PMID:<n>`` where possible.

    ``fetcher`` is required only for forms needing a network lookup; without it,
    such forms resolve to None rather than guessing.
    """
    raw = reference.strip()

    match = _PMID.match(raw)
    if match:
        return Resolution(raw, _pmid(match.group(1)), "direct", "already a PMID")

    pmc = _PMCID.search(raw)
    if pmc:
        if fetcher is None:
            return Resolution(
                raw, None, "unresolved", "PMC form requires a lookup; no fetcher supplied"
            )
        try:
            payload, _ = fetch_json(
                fetcher, f"{ID_CONVERTER}?ids=PMC{pmc.group(1)}&format=json"
            )
        except RetrievalError as error:
            return Resolution(raw, None, "unresolved", f"ID converter failed: {error}")
        records = payload.get("records") if isinstance(payload, dict) else None
        if isinstance(records, list):
            for record in records:
                if isinstance(record, dict) and record.get("pmid"):
                    return Resolution(
                        raw,
                        _pmid(str(record["pmid"])),
                        "ncbi_id_converter",
                        f"PMC{pmc.group(1)} maps to PMID {record['pmid']}",
                    )
        return Resolution(
            raw, None, "unresolved", "ID converter returned no PMID for this PMC id"
        )

    candidate = _DOI_PREFIX.sub("", raw)
    if _BARE_DOI.match(candidate):
        if fetcher is None:
            return Resolution(
                raw, None, "unresolved", "DOI form requires a lookup; no fetcher supplied"
            )
        url = f"{EUROPE_PMC_SEARCH}?" + urlencode(
            {"query": f'DOI:"{candidate}"', "resultType": "lite", "format": "json"}
        )
        try:
            payload, _ = fetch_json(fetcher, url)
        except RetrievalError as error:
            return Resolution(raw, None, "unresolved", f"Europe PMC failed: {error}")
        results = (
            payload.get("resultList", {}).get("result", [])
            if isinstance(payload, dict)
            else []
        )
        for result in results:
            if isinstance(result, dict) and result.get("pmid"):
                return Resolution(
                    raw,
                    _pmid(str(result["pmid"])),
                    "europe_pmc_doi",
                    f"DOI {candidate} maps to PMID {result['pmid']}",
                )
        return Resolution(
            raw, None, "unresolved", "Europe PMC returned no PMID for this DOI"
        )

    prefix = raw.split(":", 1)[0].lower() if ":" in raw else "unknown"
    return Resolution(
        raw,
        None,
        "no_resolver",
        f"reference form {prefix!r} has no resolver in V1; it stays unverifiable",
    )


def canonical_identity(reference: str, resolution: Resolution) -> str:
    """The identity used for independence counting.

    Falls back to the upstream form so unresolved references remain distinct from
    one another rather than collapsing into a single pseudo-source.
    """
    return resolution.canonical or reference.strip()
