"""Corpus-scale detection of claim-evidence fit risks in curated data.

This needs no manual extraction and no network: every detector reads fields the
importer already parses, so it runs over all 3,289 DisMech entries.

Every output is a **risk flag for curator review, not a proven error.** Each
detector below names its own false-positive mode, because a flag list whose
precision is unstated is worse than no list: it invites either blind trust or
blanket dismissal.

The detectors encode failure modes DisMech itself documents as open issues --
chiefly that a resolvable citation with a verbatim snippet can still be attached
to a claim it does not establish (issue #10609), and that background statements
can be mistaken for results produced by the cited paper.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

PMC_IN_REFERENCE = re.compile(r"PMC(\d+)", re.IGNORECASE)
PMID_REFERENCE = re.compile(r"^PMID:\s*(\d+)$", re.IGNORECASE)
DOI_REFERENCE = re.compile(r"^(DOI:\s*)?10\.\d{4,9}/", re.IGNORECASE)

# Human-population frequency vocabularies. A frequency stated in these terms is a
# claim about people, whatever the evidence behind it was measured in.
HUMAN_FREQUENCY_TERMS = frozenset(
    {
        "OBLIGATE",
        "VERY_FREQUENT",
        "FREQUENT",
        "OCCASIONAL",
        "VERY_RARE",
        "EXCLUDED",
    }
)


class Severity(StrEnum):
    # The claim may rest on evidence that cannot establish it.
    HIGH = "high"
    # The claim's support is weaker or narrower than its wording implies.
    MEDIUM = "medium"
    # A bookkeeping problem that can distort downstream reasoning.
    LOW = "low"


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: Severity
    disease_file: str
    object_path: str
    object_name: str
    detail: str
    references: tuple[str, ...]
    curator_check: str


@dataclass
class DetectorSpec:
    code: str
    severity: Severity
    question: str
    false_positive_mode: str
    documented_as: str = ""
    count: int = 0
    objects_examined: int = 0
    examples: list[Finding] = field(default_factory=list)


def _supporting(evidence: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        item
        for item in evidence
        if str(item.get("supports", "SUPPORT")).upper() == "SUPPORT"
    ]


def _evidence_list(obj: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = obj.get("evidence")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _refs(evidence: list[Mapping[str, Any]]) -> tuple[str, ...]:
    return tuple(str(item.get("reference", "")) for item in evidence if item.get("reference"))


# Paths that carry a causal mechanism claim. Several detectors are scoped to these:
# an ORPHA-only citation on a clinical-trial listing or a review citation for a
# treatment entry is ordinary practice, while the same pattern under a mechanism
# claim is a claim-fit question. Scoping keeps the list about mechanism.
MECHANISM_PATH = re.compile(
    r"^\$\.(pathophysiology\[\d+\](\.downstream\[\d+\])?"
    r"|mechanistic_hypotheses\[\d+\]"
    r"|phenotypes\[\d+\]\.sequelae\[\d+\])$"
)


def _is_mechanism_path(path: str) -> bool:
    return bool(MECHANISM_PATH.match(path))


def _name(obj: Mapping[str, Any], fallback: str) -> str:
    for key in ("name", "target", "prompt", "title"):
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:120]
    return fallback


def _walk(value: Any, path: str) -> Iterator[tuple[str, Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        yield path, value
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _mixed_identifier_forms(
    evidence: list[Mapping[str, Any]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return PMID-form and PMC-form references appearing in one evidence list.

    Confirming that two forms denote one publication needs an identifier lookup,
    which this offline detector deliberately does not perform. Co-occurrence is
    therefore reported as a candidate for resolution rather than as a duplicate.
    """
    pmids: list[str] = []
    pmcs: list[str] = []
    for item in evidence:
        reference = str(item.get("reference", "")).strip()
        if not reference:
            continue
        if PMID_REFERENCE.match(reference):
            pmids.append(reference)
        elif PMC_IN_REFERENCE.search(reference):
            pmcs.append(reference)
    return tuple(dict.fromkeys(pmids)), tuple(dict.fromkeys(pmcs))


def detectors() -> dict[str, DetectorSpec]:
    return {
        "BACKGROUND_ONLY_SUPPORT": DetectorSpec(
            code="BACKGROUND_ONLY_SUPPORT",
            severity=Severity.HIGH,
            question=(
                "Is every supporting citation marked as background rather than as the "
                "cited paper's own result?"
            ),
            false_positive_mode=(
                "A curator may mark a quote BACKGROUND because the sentence sits in an "
                "introduction while the paper does also report the result elsewhere. "
                "The flag identifies the quote used, not the paper's full content."
            ),
            documented_as="DisMech issue #10609 (claim-evidence fit)",
        ),
        "REVIEW_ONLY_SUPPORT": DetectorSpec(
            code="REVIEW_ONLY_SUPPORT",
            severity=Severity.MEDIUM,
            question=(
                "Is every supporting citation a review synthesis rather than a primary "
                "result?"
            ),
            false_positive_mode=(
                "A review can be the appropriate source for a settled, textbook-level "
                "statement. Scoped to mechanism claims only. The flag is about provenance "
                "depth, not correctness."
            ),
        ),
        "DIRECT_EDGE_NO_EVIDENCE": DetectorSpec(
            code="DIRECT_EDGE_NO_EVIDENCE",
            severity=Severity.MEDIUM,
            question=(
                "Does an edge asserting a DIRECT causal link carry no evidence of its "
                "own?"
            ),
            false_positive_mode=(
                "Only flagged when neither endpoint node carries supporting evidence "
                "either, so the common pattern of evidence sitting on nodes is excluded. "
                "A curator may still consider the transition self-evident."
            ),
        ),
        "HUMAN_FREQUENCY_MODEL_ONLY": DetectorSpec(
            code="HUMAN_FREQUENCY_MODEL_ONLY",
            severity=Severity.HIGH,
            question=(
                "Does a phenotype state a human-population frequency while every "
                "supporting citation is model-organism evidence?"
            ),
            false_positive_mode=(
                "The frequency may have been taken from a source the curator did not "
                "attach, so the flag means the stated evidence cannot support the stated "
                "frequency, not that the frequency is wrong."
            ),
            documented_as="documented upstream limitation",
        ),
        "UNVERIFIABLE_SOLE_SUPPORT": DetectorSpec(
            code="UNVERIFIABLE_SOLE_SUPPORT",
            severity=Severity.MEDIUM,
            question=(
                "Is every supporting citation in a reference form that cannot be "
                "resolved or checked (ORPHA, a bare URL, a registry id)?"
            ),
            false_positive_mode=(
                "An ORPHA or registry reference can be an entirely appropriate source. "
                "Scoped to mechanism claims only, since such references are ordinary for "
                "clinical and prevalence entries. Marks what no automated check can "
                "verify, which matters for auditability rather than for truth."
            ),
        ),
        "DUAL_FORM_CITATION": DetectorSpec(
            code="DUAL_FORM_CITATION",
            severity=Severity.LOW,
            question=(
                "Is one publication cited in two identifier forms in the same evidence "
                "list, so it does not deduplicate?"
            ),
            false_positive_mode=(
                "Detected offline, so co-occurrence of a PMID form and a PMC form is "
                "reported without confirming they denote one publication. Two forms may "
                "genuinely be different records, such as a preprint and its journal "
                "version. Confirming identity needs an identifier lookup."
            ),
        ),
        "CONFIDENCE_CONTRADICTS_EVIDENCE": DetectorSpec(
            code="CONFIDENCE_CONTRADICTS_EVIDENCE",
            severity=Severity.HIGH,
            question=(
                "Is a mechanism marked ESTABLISHED while carrying its own REFUTE or "
                "NO_EVIDENCE citations?"
            ),
            false_positive_mode=(
                "A refuting citation may bear on a narrower sub-claim than the node as a "
                "whole, which is a legitimate curation pattern. The flag asks whether the "
                "confidence label still fits."
            ),
        ),
    }


def audit_document(document: Mapping[str, Any], filename: str) -> list[Finding]:
    """Run every detector over one disease document."""
    findings: list[Finding] = []

    for path, obj in _walk(document, "$"):
        evidence = _evidence_list(obj)
        if not evidence:
            continue
        supporting = _supporting(evidence)
        roles = [
            str(item.get("quote_role") or "").upper()
            for item in supporting
            if item.get("quote_role")
        ]
        name = _name(obj, path)

        if supporting and roles and len(roles) == len(supporting):
            if all(role == "BACKGROUND" for role in roles):
                findings.append(
                    Finding(
                        code="BACKGROUND_ONLY_SUPPORT",
                        severity=Severity.HIGH,
                        disease_file=filename,
                        object_path=path,
                        object_name=name,
                        detail=(
                            f"All {len(supporting)} supporting citation(s) are marked "
                            "BACKGROUND, so the quoted text is attributed to earlier work "
                            "rather than to the cited paper's own findings."
                        ),
                        references=_refs(supporting),
                        curator_check=(
                            "Confirm the cited paper itself establishes this, or attach a "
                            "primary result."
                        ),
                    )
                )
            elif all(role == "REVIEW_SYNTHESIS" for role in roles) and _is_mechanism_path(
                path
            ):
                findings.append(
                    Finding(
                        code="REVIEW_ONLY_SUPPORT",
                        severity=Severity.MEDIUM,
                        disease_file=filename,
                        object_path=path,
                        object_name=name,
                        detail=(
                            f"All {len(supporting)} supporting citation(s) are review "
                            "syntheses; no primary result is attached."
                        ),
                        references=_refs(supporting),
                        curator_check="Trace the review to the primary source it summarises.",
                    )
                )

        polarity = {str(item.get("supports", "SUPPORT")).upper() for item in evidence}
        confidence = str(obj.get("mechanism_confidence") or "").upper()
        if confidence == "ESTABLISHED" and ({"REFUTE", "NO_EVIDENCE"} & polarity):
            contrary = [
                item
                for item in evidence
                if str(item.get("supports", "")).upper() in {"REFUTE", "NO_EVIDENCE"}
            ]
            findings.append(
                Finding(
                    code="CONFIDENCE_CONTRADICTS_EVIDENCE",
                    severity=Severity.HIGH,
                    disease_file=filename,
                    object_path=path,
                    object_name=name,
                    detail=(
                        "Mechanism confidence is ESTABLISHED while the same object carries "
                        f"{len(contrary)} REFUTE or NO_EVIDENCE citation(s)."
                    ),
                    references=_refs(contrary),
                    curator_check=(
                        "Decide whether the refuting evidence narrows the claim, and "
                        "whether ESTABLISHED remains the right label."
                    ),
                )
            )

        if supporting:
            unverifiable = [
                item
                for item in supporting
                if not PMID_REFERENCE.match(str(item.get("reference", "")).strip())
                and not PMC_IN_REFERENCE.search(str(item.get("reference", "")))
                and not DOI_REFERENCE.match(str(item.get("reference", "")).strip())
            ]
            if len(unverifiable) == len(supporting) and _is_mechanism_path(path):
                findings.append(
                    Finding(
                        code="UNVERIFIABLE_SOLE_SUPPORT",
                        severity=Severity.MEDIUM,
                        disease_file=filename,
                        object_path=path,
                        object_name=name,
                        detail=(
                            f"All {len(supporting)} supporting citation(s) use a reference "
                            "form with no resolver, so no automated check can verify them."
                        ),
                        references=_refs(supporting),
                        curator_check="Add a PMID or DOI where one exists for the same source.",
                    )
                )

        pmid_forms, pmc_forms = _mixed_identifier_forms(evidence)
        if pmid_forms and pmc_forms:
            findings.append(
                Finding(
                    code="DUAL_FORM_CITATION",
                    severity=Severity.LOW,
                    disease_file=filename,
                    object_path=path,
                    object_name=name,
                    detail=(
                        f"This evidence list mixes {len(pmid_forms)} PMID-form and "
                        f"{len(pmc_forms)} PMC-form reference(s). If any pair denotes one "
                        "publication it will not deduplicate, and independence counting "
                        "can treat one study as two."
                    ),
                    references=(*pmid_forms, *pmc_forms),
                    curator_check=(
                        "Resolve the PMC identifiers to PMIDs and normalise to one form "
                        "per source."
                    ),
                )
            )

    nodes = [
        node for node in (document.get("pathophysiology") or []) if isinstance(node, Mapping)
    ]
    evidence_by_label = {
        str(node.get("name", "")): bool(_supporting(_evidence_list(node))) for node in nodes
    }
    for index, node in enumerate(nodes):
        for edge_index, edge in enumerate(node.get("downstream") or []):
            if not isinstance(edge, Mapping):
                continue
            if str(edge.get("causal_link_type") or "").upper() != "DIRECT":
                continue
            if _evidence_list(edge):
                continue
            # Evidence may legitimately sit on an endpoint node instead. Only flag the
            # transition when neither endpoint carries supporting evidence either,
            # which is the genuinely unsupported case rather than a curation style.
            source_has = evidence_by_label.get(str(node.get("name", "")), False)
            target_has = evidence_by_label.get(str(edge.get("target", "")), False)
            if source_has or target_has:
                continue
            findings.append(
                Finding(
                    code="DIRECT_EDGE_NO_EVIDENCE",
                    severity=Severity.MEDIUM,
                    disease_file=filename,
                    object_path=f"pathophysiology[{index}].downstream[{edge_index}]",
                    object_name=(
                        f"{_name(node, 'node')} -> {str(edge.get('target', ''))[:80]}"
                    ),
                    detail=(
                        "Edge asserts a DIRECT causal link and carries no evidence of its "
                        "own, and neither endpoint node carries supporting evidence."
                    ),
                    references=(),
                    curator_check=(
                        "Attach evidence for the transition, or soften the causal link "
                        "type to reflect what the node evidence supports."
                    ),
                )
            )

    for index, phenotype in enumerate(document.get("phenotypes") or []):
        if not isinstance(phenotype, Mapping):
            continue
        frequency = str(phenotype.get("frequency") or "").upper()
        if frequency not in HUMAN_FREQUENCY_TERMS:
            continue
        supporting = _supporting(_evidence_list(phenotype))
        if not supporting:
            continue
        sources = {
            str(item.get("evidence_source") or "").upper() for item in supporting
        }
        if sources == {"MODEL_ORGANISM"}:
            findings.append(
                Finding(
                    code="HUMAN_FREQUENCY_MODEL_ONLY",
                    severity=Severity.HIGH,
                    disease_file=filename,
                    object_path=f"phenotypes[{index}]",
                    object_name=_name(phenotype, "phenotype"),
                    detail=(
                        f"Phenotype states the human frequency {frequency} while all "
                        f"{len(supporting)} supporting citation(s) are model-organism "
                        "evidence."
                    ),
                    references=_refs(supporting),
                    curator_check=(
                        "Attach a human source for the frequency, or remove the frequency "
                        "claim."
                    ),
                )
            )

    return findings
