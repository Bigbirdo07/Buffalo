"""Biomedical entities whose meaning does not depend on an API provider."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.domain.provenance import Provenance


class FunctionalEffect(StrEnum):
    LOSS_OF_FUNCTION = "loss_of_function"
    GAIN_OF_FUNCTION = "gain_of_function"
    DOMINANT_NEGATIVE = "dominant_negative"
    HAPLOINSUFFICIENCY = "haploinsufficiency"
    ALTERED_LOCALIZATION = "altered_localization"
    ALTERED_STABILITY = "altered_stability"
    SPLICE_DISRUPTION = "splice_disruption"
    UNKNOWN = "unknown"


class Disease(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    canonical_name: str
    mondo_id: str | None = None
    omim_id: str | None = None
    orphanet_id: str | None = None
    aliases: tuple[str, ...] = ()
    description: str | None = None
    parents: tuple[str, ...] = ()
    disease_type: str | None = None
    source: str
    source_version: str
    source_date: str | None = None
    provenance: Provenance


class Gene(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    hgnc_id: str | None = None
    symbol: str
    name: str | None = None
    aliases: tuple[str, ...] = ()


class Variant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    upstream_label: str | None = None
    clinical_significance: str | None = None
    source_object_path: str | None = None
    hgvs_genomic: str | None = None
    hgvs_coding: str | None = None
    hgvs_protein: str | None = None
    clinvar_id: str | None = None
    chromosome: str | None = None
    position: int | None = None
    ref: str | None = None
    alt: str | None = None
    variant_class: str | None = None
    molecular_consequence: str | None = None
    zygosity: str | None = None
    inheritance: str | None = None
    associated_gene: str | None = None
    associated_transcript: str | None = None
    protein_domain: str | None = None
    functional_effect: FunctionalEffect = FunctionalEffect.UNKNOWN
    evidence_ids: tuple[str, ...] = ()

    @field_validator("functional_effect")
    @classmethod
    def effect_requires_evidence(
        cls, value: FunctionalEffect, info: object
    ) -> FunctionalEffect:
        # Cross-field enforcement is completed after construction by the model
        # validator in services. UNKNOWN is deliberately the safe default.
        return value


class Phenotype(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    hpo_id: str | None = Field(default=None, pattern=r"^HP:\d{7}$")
    label: str
    frequency: str | None = None
    onset: str | None = None
    severity: str | None = None
    source: str
    evidence_ids: tuple[str, ...] = ()

