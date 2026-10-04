"""Deterministic citation and quotation checks.

No model judgement is involved: an identifier either resolves, a title either
matches, and a quoted span is either located in retrieved text or it is not.
"Not located" is reported as such; it is never silently upgraded.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from atlas.domain.evidence import CitationStatus, CitationVerification, EvidenceItem

_ELLIPSIS = re.compile(r"\s*(?:\.\.\.|…|\[\.\.\.\])\s*")


def normalize_text(value: str) -> str:
    """Case-, punctuation- and whitespace-insensitive comparison form."""
    value = unicodedata.normalize("NFKC", value).lower()
    value = value.replace("α", "alpha").replace("β", "beta").replace("→", " ")
    return " ".join(re.findall(r"[a-z0-9]+", value))


@dataclass(frozen=True, slots=True)
class SourceText:
    location: str  # "title", "abstract", or "full_text"
    text: str
    snapshot_sha256: str


def locate_span(span: str, sources: tuple[SourceText, ...]) -> str | None:
    """Return the first location containing every ellipsis-separated fragment."""
    fragments = [normalize_text(part) for part in _ELLIPSIS.split(span) if part.strip()]
    fragments = [fragment for fragment in fragments if fragment]
    if not fragments:
        return None
    for source in sources:
        haystack = normalize_text(source.text)
        if all(fragment in haystack for fragment in fragments):
            return source.location
    return None


def titles_match(expected: str | None, observed: str) -> bool | None:
    if not expected:
        return None
    left, right = normalize_text(expected), normalize_text(observed)
    return left == right or (bool(left) and (left in right or right in left))


def verify_citation(
    item: EvidenceItem,
    *,
    resolved_title: str | None,
    sources: tuple[SourceText, ...],
    canonical_identifier: str | None = None,
) -> CitationVerification:
    """Check one evidence pointer deterministically.

    ``canonical_identifier`` is supplied when the upstream reference form was not
    a PMID but was mapped to one (a PMC URL, a DOI). Resolution makes the pointer
    checkable; it does not make the quoted span verified, because the text behind
    a resolved identifier may still be unavailable.
    """
    identifier = item.pmid or item.doi or item.pmcid or item.other_reference or ""
    checked = tuple(source.location for source in sources)
    hashes = tuple(source.snapshot_sha256 for source in sources)
    full_text_available = any(source.location == "full_text" for source in sources)
    effective = item.pmid or canonical_identifier

    if effective is None:
        return CitationVerification(
            evidence_id=item.evidence_id,
            identifier=identifier,
            status=CitationStatus.NOT_CHECKABLE,
            identifier_resolved=False,
            canonical_identifier=None,
            full_text_available=full_text_available,
            title_matches=None,
            span_location=None,
            texts_checked=(),
            note=(
                "Reference form has no deterministic resolver in V1; it was neither "
                "a PMID nor resolvable to one."
            ),
        )
    if resolved_title is None:
        return CitationVerification(
            evidence_id=item.evidence_id,
            identifier=identifier,
            status=CitationStatus.UNRESOLVED,
            identifier_resolved=False,
            canonical_identifier=canonical_identifier,
            full_text_available=full_text_available,
            title_matches=None,
            span_location=None,
            texts_checked=checked,
            note="Identifier did not resolve in PubMed efetch.",
        )

    title_ok = titles_match(item.title, resolved_title)
    location = locate_span(item.exact_supported_span, sources)
    if title_ok is False:
        status = CitationStatus.TITLE_MISMATCH
        note = f"Upstream title differs from the resolved title {resolved_title!r}."
    elif location is not None:
        status = CitationStatus.VERIFIED
        note = f"Span located verbatim (normalized) in {location}."
    elif full_text_available:
        status = CitationStatus.SPAN_NOT_LOCATED
        note = (
            "Full text was retrieved and the quoted span was not found in it. This "
            "may indicate a misquotation or a misattributed source and needs review."
        )
    else:
        status = CitationStatus.UPSTREAM_ATTESTED
        note = (
            "Identifier resolves, but the source text could not be retrieved "
            f"(available: {', '.join(checked) or 'none'}), so the upstream curator's "
            "verbatim snippet could not be independently located. The quotation is "
            "neither confirmed nor impugned; it may qualify a claim but cannot alone "
            "support or contradict one."
        )
    return CitationVerification(
        evidence_id=item.evidence_id,
        identifier=identifier,
        status=status,
        identifier_resolved=True,
        canonical_identifier=canonical_identifier,
        full_text_available=full_text_available,
        title_matches=title_ok,
        span_location=location,
        texts_checked=checked,
        source_snapshot_sha256=hashes,
        note=note,
    )
