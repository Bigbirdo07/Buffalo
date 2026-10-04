"""Build a mechanistic fingerprint from an imported disease.

Everything here is derived from objects the importer already normalized, so the
fingerprint inherits the import's provenance guarantees rather than re-parsing
upstream YAML with looser rules.

Deliberate choices a reader should be able to check:

* **Evidence counts travel with features.** A feature asserted by a node carrying
  twelve citations is not the same as one asserted in passing, and candidate
  ranking should be able to tell the difference.
* **Directional modifiers are kept.** Two diseases that perturb one process in
  opposite directions are not mechanistically equivalent, so INCREASED and
  DECREASED are preserved rather than flattened into "shares this process".
* **Mechanism node labels are normalized but never merged across diseases.**
  Free-text node names are curator prose; matching them exactly across entries is
  a weak signal, so they are kept separate from ontology-grounded features.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from atlas.adapters.dismech.importer import ImportedDisease
from atlas.domain.fingerprint import (
    SLOT_CLASSES,
    DiseaseMechanismFingerprint,
    FeatureClass,
    FingerprintCoverage,
    FingerprintFeature,
)

# Upstream variant/effect vocabulary worth carrying into compatibility checks.
VARIANT_EFFECT_TERMS = (
    "loss_of_function",
    "loss of function",
    "gain_of_function",
    "gain of function",
    "dominant_negative",
    "dominant negative",
    "haploinsufficiency",
    "nonsense",
    "missense",
    "frameshift",
    "truncating",
    "deletion",
    "duplication",
    "splice",
)
THERAPEUTIC_TERMS = (
    "gene therapy",
    "gene replacement",
    "gene addition",
    "antisense",
    "aso",
    "rnai",
    "sirna",
    "small molecule",
    "enzyme replacement",
    "substrate reduction",
    "chaperone",
    "protein stabilization",
    "transplant",
    "immunosuppress",
)
MODEL_ORGANISM_TERMS = {
    "mus musculus": "Mus musculus",
    "mouse": "Mus musculus",
    "danio rerio": "Danio rerio",
    "zebrafish": "Danio rerio",
    "drosophila": "Drosophila melanogaster",
    "caenorhabditis": "Caenorhabditis elegans",
    "c. elegans": "Caenorhabditis elegans",
    "rattus": "Rattus norvegicus",
    "rat": "Rattus norvegicus",
    "saccharomyces": "Saccharomyces cerevisiae",
    "yeast": "Saccharomyces cerevisiae",
}
_WORD = re.compile(r"[a-z0-9]+")


def _normalize_label(value: str) -> str:
    return " ".join(_WORD.findall(value.lower()))


def _scan(text: str, terms: tuple[str, ...]) -> set[str]:
    lowered = text.lower()
    return {term for term in terms if term in lowered}


@dataclass
class _Accumulator:
    """Mutable gather-point for one feature seen across several upstream objects."""

    label: str
    feature_class: FeatureClass
    slot: str
    paths: set[str] = field(default_factory=set)
    evidence: int = 0
    modifiers: set[str] = field(default_factory=set)


def build_fingerprint(imported: ImportedDisease) -> DiseaseMechanismFingerprint:
    """Derive a fingerprint from one imported disease."""
    collected: dict[str, _Accumulator] = {}

    def add(
        feature_id: str,
        label: str,
        feature_class: FeatureClass,
        slot: str,
        path: str,
        evidence: int,
        modifier: str | None = None,
    ) -> None:
        entry = collected.setdefault(
            feature_id, _Accumulator(label=label, feature_class=feature_class, slot=slot)
        )
        entry.paths.add(path)
        entry.evidence += evidence
        if modifier:
            entry.modifiers.add(modifier.upper())

    evidence_by_node = {node.id: len(node.evidence_ids) for node in imported.graph.nodes}

    for node in imported.graph.nodes:
        path = node.provenance.source_object_path
        evidence = evidence_by_node.get(node.id, 0)
        for annotation in node.annotations:
            mapping = SLOT_CLASSES.get(annotation.slot)
            if mapping is None:
                continue
            feature_class, _prefix = mapping
            identifier = annotation.term_id or (
                f"text:{_normalize_label(annotation.preferred_term or '')}"
            )
            label = annotation.term_label or annotation.preferred_term or identifier
            if identifier in {"text:", ""}:
                continue
            add(
                identifier,
                label,
                feature_class,
                annotation.slot,
                path,
                evidence,
                annotation.modifier,
            )

    # Phenotypes: HPO where grounded, otherwise the curated label.
    phenotype_ids: list[str] = []
    for phenotype in imported.phenotypes:
        identifier = phenotype.hpo_id or f"text:{_normalize_label(phenotype.label)}"
        if phenotype.hpo_id:
            phenotype_ids.append(phenotype.hpo_id)
        add(
            identifier,
            phenotype.label,
            FeatureClass.PHENOTYPE,
            "phenotypes",
            f"phenotypes[{imported.phenotypes.index(phenotype)}]",
            len(phenotype.evidence_ids),
        )

    gene_ids: list[str] = []
    for gene in imported.genes:
        identifier = gene.hgnc_id or f"text:{_normalize_label(gene.symbol)}"
        if gene.hgnc_id:
            gene_ids.append(gene.hgnc_id)
        add(identifier, gene.symbol, FeatureClass.GENETIC, "genetic", "genetic", 0)

    # Variant effects and therapeutic modalities come from preserved records,
    # scanned conservatively: a term is recorded only when it appears literally.
    variant_effects: set[str] = set()
    therapeutic: set[str] = set()
    organisms: set[str] = set()
    for record in imported.preserved_records:
        payload = record.provenance.source_payload
        text = " ".join(
            str(value) for value in payload.values() if isinstance(value, str | int | float)
        )
        if record.section in {"genetic", "variants"}:
            variant_effects |= _scan(text, VARIANT_EFFECT_TERMS)
        if record.section == "treatments":
            therapeutic |= _scan(text, THERAPEUTIC_TERMS)
        if record.section in {"animal_models", "experimental_models"}:
            lowered = text.lower()
            for needle, canonical in MODEL_ORGANISM_TERMS.items():
                if needle in lowered:
                    organisms.add(canonical)

    for organism in sorted(organisms):
        add(
            f"organism:{organism}",
            organism,
            FeatureClass.MODEL_ORGANISM,
            "animal_models",
            "animal_models",
            0,
        )
    for modality in sorted(therapeutic):
        add(
            f"modality:{modality}",
            modality,
            FeatureClass.THERAPEUTIC,
            "treatments",
            "treatments",
            0,
        )

    features = tuple(
        FingerprintFeature(
            feature_id=feature_id,
            label=entry.label[:200],
            feature_class=entry.feature_class,
            slot=entry.slot,
            source_object_paths=tuple(sorted(entry.paths)),
            evidence_count=entry.evidence,
            modifiers=tuple(sorted(entry.modifiers)),
        )
        for feature_id, entry in sorted(collected.items())
    )

    by_class: defaultdict[str, int] = defaultdict(int)
    for feature in features:
        by_class[feature.feature_class.value] += 1
    missing = tuple(
        item.value for item in FeatureClass if by_class.get(item.value, 0) == 0
    )

    return DiseaseMechanismFingerprint(
        disease_id=imported.disease.id,
        disease_name=imported.disease.canonical_name,
        mondo_id=imported.disease.mondo_id,
        source_file=imported.snapshot.source_locator,
        source_version=imported.disease.source_version,
        source_sha256=imported.snapshot.sha256,
        features=features,
        phenotype_ids=tuple(sorted(set(phenotype_ids))),
        gene_ids=tuple(sorted(set(gene_ids))),
        mechanism_node_labels=tuple(
            sorted({node.label for node in imported.graph.nodes if node.label})
        ),
        variant_effects=tuple(sorted(variant_effects)),
        therapeutic_modalities=tuple(sorted(therapeutic)),
        model_organisms=tuple(sorted(organisms)),
        coverage=FingerprintCoverage(
            features_by_class=dict(sorted(by_class.items())),
            ontology_grounded_features=sum(
                1 for item in features if item.is_ontology_grounded
            ),
            free_text_features=sum(
                1 for item in features if not item.is_ontology_grounded
            ),
            mechanism_nodes=len(imported.graph.nodes),
            mechanism_edges=len(imported.graph.edges),
            evidence_items=len(imported.evidence),
            missing_dimensions=missing,
        ),
    )
