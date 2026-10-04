"""Resolve gene symbols to the protein names literature actually uses.

This adapter exists because of a measured pipeline failure. A co-mention search
for two diseases built from their HGNC gene symbols returned zero hits, while
the relevant literature does discuss the pair -- under the proteins' common
names rather than their gene symbols. Searching a gene symbol alone silently
misses the papers that matter, and a zero-hit search is indistinguishable from
"no relationship exists" unless the alias problem is fixed.

Aliases come from UniProt: the reviewed (Swiss-Prot) human entry for a gene
symbol, taking the recommended protein name plus short names and alternative
names. Responses are snapshot-cached and content-addressed like every other
retrieval in this project, so a run is reproducible offline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import quote

from atlas.adapters.literature.client import RetrievalError, SnapshotFetcher

UNIPROT_SEARCH = "https://rest.uniprot.org/uniprotkb/search"


@dataclass(frozen=True)
class ProteinNames:
    gene_symbol: str
    accession: str | None
    recommended_name: str | None
    short_names: tuple[str, ...]
    alternative_names: tuple[str, ...]
    snapshot_sha256: str | None = None

    @property
    def common_acronyms(self) -> tuple[str, ...]:
        """Short names papers actually use, mined from descriptive protein names.

        UniProt names proteins descriptively -- "E3 ubiquitin-protein ligase
        CHIP" -- while the literature uses the trailing acronym. Searching only
        the descriptive phrase misses nearly every relevant paper, which is the
        failure that motivated this adapter.

        Only a trailing token that is predominantly uppercase is taken, and only
        when it is not simply the gene symbol again. Acronyms are collision-prone
        (this project has already been bitten by one that doubles as an assay
        name), so they are returned separately and are only safe in a query that
        is constrained by another entity.
        """
        found: list[str] = []
        for name in (self.recommended_name, *self.alternative_names):
            if not name:
                continue
            token = name.split()[-1].strip(",.;()")
            if (
                3 <= len(token) <= 8
                and sum(character.isupper() for character in token) >= len(token) - 1
                and token.upper() != self.gene_symbol.upper()
                and token.upper() not in {item.upper() for item in found}
            ):
                found.append(token)
        return tuple(found)

    @property
    def search_aliases(self) -> tuple[str, ...]:
        """Alias strings worth putting in a literature query, best first.

        Order matters because callers cap the list: the gene symbol and the
        common acronym are what publications use, so they must survive the cap.
        Very short tokens are dropped, since a two-character term matches far
        too much and a false hit is worse than a missed one once it enters the
        evidence set.
        """
        candidates = [
            self.gene_symbol,
            *self.common_acronyms,
            *self.short_names,
            self.recommended_name or "",
            *self.alternative_names,
        ]
        seen: list[str] = []
        for item in candidates:
            cleaned = item.strip()
            if len(cleaned) < 3 or cleaned.lower() in {x.lower() for x in seen}:
                continue
            seen.append(cleaned)
        return tuple(seen)


class UniProtClient:
    """Minimal reviewed-human-entry lookup, snapshot cached."""

    def __init__(self, fetcher: SnapshotFetcher) -> None:
        self.fetcher = fetcher

    def protein_names(self, gene_symbol: str) -> ProteinNames:
        query = quote(
            f"(gene_exact:{gene_symbol}) AND (organism_id:9606) AND (reviewed:true)"
        )
        url = (
            f"{UNIPROT_SEARCH}?query={query}&format=json"
            "&fields=accession,protein_name&size=1"
        )
        try:
            response = self.fetcher.fetch(url)
            payload, digest = response.body, response.sha256
        except RetrievalError:
            # A failed lookup degrades to the bare symbol rather than aborting:
            # the search still runs, with its coverage recorded as narrower.
            return ProteinNames(gene_symbol, None, None, (), ())
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return ProteinNames(gene_symbol, None, None, (), (), digest)

        results = data.get("results") or []
        if not results:
            return ProteinNames(gene_symbol, None, None, (), (), digest)
        entry = results[0]
        description = entry.get("proteinDescription") or {}
        recommended = description.get("recommendedName") or {}
        full = (recommended.get("fullName") or {}).get("value")
        shorts = tuple(
            item.get("value")
            for item in (recommended.get("shortNames") or [])
            if item.get("value")
        )
        alternatives: list[str] = []
        for alternative in description.get("alternativeNames") or []:
            value = (alternative.get("fullName") or {}).get("value")
            if value:
                alternatives.append(value)
            for short in alternative.get("shortNames") or []:
                if short.get("value"):
                    alternatives.append(short["value"])
        return ProteinNames(
            gene_symbol=gene_symbol,
            accession=entry.get("primaryAccession"),
            recommended_name=full,
            short_names=shorts,
            alternative_names=tuple(alternatives),
            snapshot_sha256=digest,
        )
