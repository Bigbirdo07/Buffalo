"""Europe PMC text-mined annotations, used to enrich a mechanistic bridge.

What this is, stated plainly because the distinction matters: Europe PMC runs
its own text mining over the literature and serves the result as typed, section
-tagged annotations. It is a derived source, not the article. For a paywalled
paper the annotations available may cover only the title and abstract, and this
adapter reports which sections it actually saw rather than implying it read the
whole paper.

Why it is worth using: the annotations carry two things raw abstract text does
not. They are typed (Gene Function, Gene Disease Relationship, Pathway, Gene
Ontology, Experimental Methods), and they are section-tagged, so a claim made in
a title or abstract can be distinguished from one buried in a discussion.

What it cannot do: an annotation does not say whether a sentence reports the
paper's own result or restates someone else's. That judgement is made separately
from the sentence's own assertion language, and a term that cannot be classified
must not be allowed to strengthen a bridge.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum

from atlas.adapters.literature.client import RetrievalError, SnapshotFetcher

ANNOTATIONS_API = "https://www.ebi.ac.uk/europepmc/annotations_api/annotationsByArticleIds"

# Types whose annotations can bear on a mechanistic bridge. Experimental Methods
# and Chemicals describe how a study was done, not what it found, so they are
# retrieved for context but never refine a bridge.
MECHANISTIC_TYPES = frozenset(
    {"Gene Function", "Gene Disease Relationship", "Pathway", "Gene Ontology"}
)

# Language by which a paper claims a finding as its own. Matching this is what
# separates a demonstrated result from a restated one, and it is the only basis
# on which an annotation is allowed to strengthen a bridge.
_PRIMARY_ASSERTION = re.compile(
    r"\b(we (show|demonstrate|report|find|identify|establish)\w*|"
    r"this (study|work|report) (demonstrat\w+|show\w+|establish\w+|identif\w+)|"
    r"here we\b|our (data|results|findings) (show|demonstrate|indicate|establish))",
    re.IGNORECASE,
)
# Language marking a statement as someone else's finding.
_BACKGROUND_ASSERTION = re.compile(
    r"\b(previously|previous stud\w+|has been (shown|reported|demonstrated)|"
    r"it is (known|well established)|others have|reported that|"
    r"earlier work)\b",
    re.IGNORECASE,
)


class FindingRole(StrEnum):
    """How a statement relates to the paper that contains it."""

    PRIMARY_EXPERIMENTAL_RESULT = "PRIMARY_EXPERIMENTAL_RESULT"
    SECONDARY_ANALYSIS = "SECONDARY_ANALYSIS"
    AUTHOR_INTERPRETATION = "AUTHOR_INTERPRETATION"
    BACKGROUND_STATEMENT = "BACKGROUND_STATEMENT"
    CITED_EXTERNAL_CLAIM = "CITED_EXTERNAL_CLAIM"
    NOT_RELEVANT = "NOT_RELEVANT"


@dataclass(frozen=True)
class MinedFinding:
    """One typed annotation with its span, section and assessed role."""

    source_id: str
    annotation_type: str
    exact: str
    sentence: str
    section: str
    role: FindingRole
    snapshot_sha256: str | None = None

    @property
    def can_refine_bridge(self) -> bool:
        """Only a demonstrated finding of a mechanistic type may refine a bridge."""
        return (
            self.role is FindingRole.PRIMARY_EXPERIMENTAL_RESULT
            and self.annotation_type in MECHANISTIC_TYPES
        )


@dataclass(frozen=True)
class ArticleAnnotations:
    source_id: str
    findings: tuple[MinedFinding, ...]
    sections_seen: tuple[str, ...]
    retrieved: bool
    failure_reason: str | None = None

    @property
    def full_text_sections_present(self) -> bool:
        """Whether anything beyond title and abstract was annotated.

        False means the mining covered only the front matter, so this run has
        NOT read the paper and must not claim to have.
        """
        # "unknown" does not count. An untagged annotation proves nothing about
        # where it came from, and treating it as full text would let this run
        # claim to have read a paper it did not retrieve.
        front = {"title", "abstract", "unknown", ""}
        return any(
            section.split("(")[0].strip().casefold() not in front
            for section in self.sections_seen
        )


def classify_role(sentence: str) -> FindingRole:
    """Assess whether a sentence reports the paper's own result.

    Conservative by construction: a sentence with no assertion language is
    BACKGROUND, not PRIMARY, because the cost of wrongly promoting background to
    a demonstrated finding is a bridge that overstates what is known. Background
    language is checked first, since a sentence containing both is most likely
    describing prior work before contrasting it.
    """
    if _BACKGROUND_ASSERTION.search(sentence):
        return FindingRole.BACKGROUND_STATEMENT
    if _PRIMARY_ASSERTION.search(sentence):
        return FindingRole.PRIMARY_EXPERIMENTAL_RESULT
    return FindingRole.BACKGROUND_STATEMENT


class EuropePmcAnnotationClient:
    def __init__(self, fetcher: SnapshotFetcher) -> None:
        self.fetcher = fetcher

    def annotations(self, pmid: str) -> ArticleAnnotations:
        identifier = pmid.replace("PMID:", "").strip()
        url = (
            f"{ANNOTATIONS_API}?articleIds=MED:{identifier}&format=JSON"
        )
        try:
            response = self.fetcher.fetch(url)
        except RetrievalError as error:
            return ArticleAnnotations(
                source_id=pmid, findings=(), sections_seen=(), retrieved=False,
                failure_reason=str(error)[:200],
            )
        try:
            payload = json.loads(response.body)
        except json.JSONDecodeError as error:
            return ArticleAnnotations(
                source_id=pmid, findings=(), sections_seen=(), retrieved=False,
                failure_reason=f"unparseable response: {error}",
            )

        records = payload if isinstance(payload, list) else [payload]
        raw: list[dict] = []
        for record in records:
            raw.extend(record.get("annotations") or [])
        findings: list[MinedFinding] = []
        sections: set[str] = set()
        for item in raw:
            section = str(item.get("section") or "unknown")
            sections.add(section)
            sentence = str(item.get("prefix") or "") + str(item.get("exact") or "")
            sentence += str(item.get("postfix") or "")
            # Europe PMC puts the whole claim in `exact` for relationship types.
            text = str(item.get("exact") or "")
            full = sentence if len(sentence) > len(text) else text
            findings.append(
                MinedFinding(
                    source_id=pmid,
                    annotation_type=str(item.get("type") or "unknown"),
                    exact=text[:400],
                    sentence=full[:600],
                    section=section,
                    role=classify_role(full),
                    snapshot_sha256=response.sha256,
                )
            )
        return ArticleAnnotations(
            source_id=pmid,
            findings=tuple(findings),
            sections_seen=tuple(sorted(sections)),
            retrieved=True,
        )
