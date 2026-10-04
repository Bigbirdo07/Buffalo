"""Mechanistic fingerprints: the interpretable feature profile of one disease.

A fingerprint is the input to cross-disease candidate generation. It exists so
that "who shares our disease characteristics" can be answered biologically
rather than by name, and so that any answer can be explained feature by feature.

Two rules shape the design:

* **No feature without provenance.** Every feature carries the upstream object
  paths it came from and how much evidence those objects hold, so a candidate
  neighbour can always be traced back to curated statements rather than to a
  similarity score.
* **A fingerprint is a description, not a claim.** Sharing features makes two
  diseases *candidate* neighbours. Whether they share a mechanism is decided by
  the refinement engine, never here.

Feature availability across the 3,289 imported diseases, measured rather than
assumed, because it determines which comparisons are possible at all:

    phenotype (HP)            100.0%     41,539 annotations
    mechanism node             99.9%     22,947
    biological process (GO)    96.7%     16,373
    cell type (CL)             89.2%      7,818
    gene (HGNC)                85.7%      7,625
    tissue (UBERON)            45.3%      3,586
    molecular function (GO)    43.8%      1,933
    cellular component (GO)    19.4%        922
    chemical entity (CHEBI)    10.6%        836
    protein complex             1.9%         70
    pathway                     0.1%         14

The last two matter: DisMech carries almost no explicit pathway or protein
complex annotation, so pathway-based candidate generation is not feasible from
this source alone. GO biological process is the usable process layer and is
treated as such throughout, which is a substitution a reader needs to know about.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

FINGERPRINT_VERSION = "disease-mechanism-fingerprint-v1"


class FeatureClass(StrEnum):
    """Interpretable grouping, so overlap can be reported per class."""

    GENETIC = "genetic"
    MOLECULAR = "molecular"
    CELLULAR = "cellular"
    CELL_TISSUE = "cell_tissue"
    PHENOTYPE = "phenotype"
    MODEL_ORGANISM = "model_organism"
    THERAPEUTIC = "therapeutic"
    MECHANISM = "mechanism"


# Upstream slot -> (class, ontology prefix the slot is expected to use).
SLOT_CLASSES: dict[str, tuple[FeatureClass, str]] = {
    "genes": (FeatureClass.GENETIC, "HGNC"),
    "gene": (FeatureClass.GENETIC, "HGNC"),
    "gene_products": (FeatureClass.MOLECULAR, ""),
    "molecular_functions": (FeatureClass.MOLECULAR, "GO"),
    "protein_complexes": (FeatureClass.MOLECULAR, ""),
    "chemical_entities": (FeatureClass.MOLECULAR, "CHEBI"),
    "biological_processes": (FeatureClass.CELLULAR, "GO"),
    "cellular_components": (FeatureClass.CELLULAR, "GO"),
    "pathways": (FeatureClass.CELLULAR, ""),
    "cell_types": (FeatureClass.CELL_TISSUE, "CL"),
    "locations": (FeatureClass.CELL_TISSUE, "UBERON"),
    "assays": (FeatureClass.MECHANISM, ""),
    "triggers": (FeatureClass.MECHANISM, ""),
}


class FingerprintFeature(BaseModel):
    """One interpretable feature, with the upstream objects that assert it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_id: str
    label: str
    feature_class: FeatureClass
    slot: str
    # Upstream object paths carrying this feature, so any match is traceable.
    source_object_paths: tuple[str, ...]
    # Evidence items attached to those objects. A feature asserted by a
    # well-evidenced node is not the same as one asserted in passing.
    evidence_count: int = Field(ge=0)
    # Upstream directional qualifiers (INCREASED, DECREASED, ...). Direction is
    # kept because two diseases perturbing one process in opposite directions are
    # not mechanistically equivalent.
    modifiers: tuple[str, ...] = ()

    @property
    def is_ontology_grounded(self) -> bool:
        return ":" in self.feature_id


class FingerprintCoverage(BaseModel):
    """What this fingerprint can and cannot support."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    features_by_class: dict[str, int]
    ontology_grounded_features: int
    free_text_features: int
    mechanism_nodes: int
    mechanism_edges: int
    evidence_items: int
    # Classes with no feature at all. A missing dimension is a limit on every
    # comparison involving this disease and must travel with it.
    missing_dimensions: tuple[str, ...]


class DiseaseMechanismFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    disease_id: str
    disease_name: str
    mondo_id: str | None = None
    source_file: str
    source_version: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    features: tuple[FingerprintFeature, ...]
    phenotype_ids: tuple[str, ...] = ()
    gene_ids: tuple[str, ...] = ()
    mechanism_node_labels: tuple[str, ...] = ()
    variant_effects: tuple[str, ...] = ()
    therapeutic_modalities: tuple[str, ...] = ()
    model_organisms: tuple[str, ...] = ()
    coverage: FingerprintCoverage
    version: str = FINGERPRINT_VERSION
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def features_of(self, feature_class: FeatureClass) -> tuple[FingerprintFeature, ...]:
        return tuple(item for item in self.features if item.feature_class is feature_class)

    def feature_ids(self, feature_class: FeatureClass | None = None) -> frozenset[str]:
        items = self.features if feature_class is None else self.features_of(feature_class)
        return frozenset(item.feature_id for item in items)

    def feature_by_id(self) -> dict[str, FingerprintFeature]:
        return {item.feature_id: item for item in self.features}
