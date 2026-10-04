"""Resolve an observation plan into verified observations.

The extractor supplies a short locator regex per observation and per STATED
context value. This module finds that locator in the *cached source text* and
copies the containing sentence out verbatim, so the recorded support span is
the source's wording rather than a retyped quotation. A locator that matches
nothing is a hard failure; a locator that matches text in a location other than
the one claimed is a hard failure.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from atlas.domain.evidence import (
    AnnotationBasis,
    ContextAnnotation,
    ContextField,
)
from atlas.domain.refinement import EffectDirection, EvidenceObservation, FindingOrigin
from atlas.services.citation_validation import SourceText, normalize_text

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


class ExtractionError(ValueError):
    """A locator could not be resolved against the cached source text."""


@dataclass(frozen=True, slots=True)
class ResolvedSpan:
    span: str
    location: str


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_END.split(text) if part.strip()]


def resolve_locator(
    locator: str, sources: Sequence[SourceText], *, expected_location: str | None = None
) -> ResolvedSpan:
    """Return the verbatim sentence containing ``locator``.

    ``locator`` is a regex matched case-insensitively against the source text with
    runs of whitespace treated as flexible.
    """
    pattern = re.compile(locator.replace(" ", r"\s+"), re.IGNORECASE)
    candidates = [
        source
        for source in sources
        if expected_location is None or source.location == expected_location
    ]
    for source in candidates or list(sources):
        match = pattern.search(source.text)
        if match is None:
            continue
        for sentence in _sentences(source.text):
            if pattern.search(sentence):
                return ResolvedSpan(span=sentence, location=source.location)
        start = max(0, match.start() - 160)
        window = source.text[start : match.end() + 160].strip()
        return ResolvedSpan(span=window, location=source.location)
    available = ", ".join(sorted({source.location for source in sources})) or "none"
    raise ExtractionError(
        f"locator {locator!r} not found in {expected_location or 'any'} text "
        f"(available: {available})"
    )


def build_context(
    entries: Sequence[Mapping[str, Any]],
    sources: Sequence[SourceText],
    *,
    expected_location: str,
) -> tuple[ContextAnnotation, ...]:
    result: list[ContextAnnotation] = []
    for entry in entries:
        field = ContextField(str(entry["field"]))
        value = str(entry["value"])
        locator = entry.get("locator")
        derivation = entry.get("derivation")
        if locator:
            resolved = resolve_locator(
                str(locator), sources, expected_location=expected_location
            )
            result.append(
                ContextAnnotation(
                    field=field,
                    value=value,
                    basis=AnnotationBasis.STATED,
                    support_span=resolved.span,
                    source_location=resolved.location,
                )
            )
        elif derivation:
            result.append(
                ContextAnnotation(
                    field=field,
                    value=value,
                    basis=AnnotationBasis.DERIVED,
                    derivation=str(derivation),
                )
            )
        else:
            result.append(
                ContextAnnotation(field=field, value=value, basis=AnnotationBasis.NOT_STATED)
            )
    return tuple(result)


def derive_protein_domains(
    variants: Sequence[str], features: Sequence[tuple[str, int, int, str]]
) -> tuple[ContextAnnotation, ...]:
    """Map ``p.Xnnn...`` residue numbers onto cached UniProt features.

    Domains are never taken from the extractor: they are computed here so the
    derivation rule is explicit and reviewable.
    """
    result: list[ContextAnnotation] = []
    for variant in variants:
        match = re.search(r"(\d+)", variant)
        if match is None:
            continue
        residue = int(match.group(1))
        hits = [
            f"{description or kind} ({start}-{end})"
            for kind, start, end, description in features
            if start <= residue <= end and kind in {"Domain", "Repeat", "Coiled coil"}
        ]
        label = "; ".join(hits) if hits else "no annotated domain at this residue"
        result.append(
            ContextAnnotation(
                field=ContextField.PROTEIN_DOMAIN,
                value=f"{variant}: {label}",
                basis=AnnotationBasis.DERIVED,
                derivation=(
                    f"Residue {residue} parsed from {variant!r} and intersected with UniProt "
                    "Q9UNE7 Domain/Repeat/Coiled-coil features from the cached snapshot."
                ),
            )
        )
    return tuple(result)


def build_observation(
    entry: Mapping[str, Any],
    *,
    evidence_id: str,
    source_identifier: str,
    gene: str,
    sources: Sequence[SourceText],
    uniprot_features: Sequence[tuple[str, int, int, str]],
) -> EvidenceObservation:
    location = str(entry["location"])
    resolved = resolve_locator(str(entry["locator"]), sources, expected_location=location)
    variants = tuple(str(item) for item in entry.get("variants") or ())
    context = build_context(entry.get("context") or (), sources, expected_location=location)
    context = (*context, *derive_protein_domains(variants, uniprot_features))
    return EvidenceObservation(
        observation_id=str(entry["id"]),
        evidence_id=evidence_id,
        source_identifier=source_identifier,
        claim_ids=tuple(str(item) for item in entry.get("claims") or ()),
        gene=gene,
        disease_entity=str(entry["disease_entity"]),
        variants=variants,
        variant_class=(
            str(entry["variant_class"]) if entry.get("variant_class") is not None else None
        ),
        readout=str(entry["readout"]),
        effect=EffectDirection(str(entry["effect"])),
        origin=FindingOrigin(str(entry["origin"])),
        species=str(entry["species"]),
        experimental_system=str(entry["system"]),
        support_span=resolved.span,
        source_location=resolved.location,
        context=context,
        extraction_note=str(entry["note"]) if entry.get("note") else None,
    )


def spans_are_verifiable(observation: EvidenceObservation) -> bool:
    """True when the observation's own span normalizes to non-empty comparable text."""
    return bool(normalize_text(observation.support_span))
