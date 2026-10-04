"""Extended, experiment-aware evidence records."""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from atlas.domain.provenance import Provenance

PMID_RE = re.compile(r"^(?:PMID:)?(\d{1,9})$")
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


class SourceSection(StrEnum):
    ABSTRACT = "abstract"
    INTRODUCTION = "introduction"
    METHODS = "methods"
    RESULTS = "results"
    DISCUSSION = "discussion"
    REVIEW_SUMMARY = "review_summary"
    UNKNOWN = "unknown"


class EvidenceRelation(StrEnum):
    SUPPORTS = "supports"
    REFUTES = "refutes"
    QUALIFIES = "qualifies"
    COMPETING = "competing"
    NEUTRAL = "neutral"


class EvidenceOrigin(StrEnum):
    PRIMARY_RESULT = "primary_result"
    CITED_BACKGROUND = "cited_background"
    REVIEW_SYNTHESIS = "review_synthesis"
    DATABASE_ASSERTION = "database_assertion"


class EvidenceModality(StrEnum):
    HUMAN_CLINICAL = "human_clinical"
    HUMAN_PATIENT_DERIVED = "human_patient_derived"
    MODEL_ORGANISM = "model_organism"
    IN_VITRO = "in_vitro"
    EX_VIVO = "ex_vivo"
    COMPUTATIONAL = "computational"
    EPIDEMIOLOGIC = "epidemiologic"
    GENETIC_ASSOCIATION = "genetic_association"
    BIOCHEMICAL = "biochemical"
    STRUCTURAL = "structural"
    REVIEW = "review"
    OTHER = "other"


class StudyDesign(StrEnum):
    RANDOMIZED_CONTROLLED_TRIAL = "randomized_controlled_trial"
    PROSPECTIVE_COHORT = "prospective_cohort"
    RETROSPECTIVE_COHORT = "retrospective_cohort"
    CASE_CONTROL = "case_control"
    CROSS_SECTIONAL = "cross_sectional"
    CASE_SERIES = "case_series"
    CASE_REPORT = "case_report"
    EXPERIMENTAL_MODEL = "experimental_model"
    CELL_EXPERIMENT = "cell_experiment"
    BIOCHEMICAL_ASSAY = "biochemical_assay"
    COMPUTATIONAL_PREDICTION = "computational_prediction"
    SYSTEMATIC_REVIEW = "systematic_review"
    META_ANALYSIS = "meta_analysis"
    NARRATIVE_REVIEW = "narrative_review"
    UNKNOWN = "unknown"


class HumanReviewStatus(StrEnum):
    UNREVIEWED = "UNREVIEWED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"


class EvidenceItem(BaseModel):
    """Objective study facts plus relation to exactly one atomic claim."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    claim_id: str
    pmid: str | None = None
    pmcid: str | None = None
    doi: str | None = None
    other_reference: str | None = None
    title: str | None = None
    authors: tuple[str, ...] = ()
    publication_year: int | None = Field(default=None, ge=1600, le=2200)
    journal: str | None = None
    exact_supported_span: str
    source_section: SourceSection = SourceSection.UNKNOWN
    evidence_relation: EvidenceRelation
    evidence_origin: EvidenceOrigin
    evidence_modality: EvidenceModality
    study_design: StudyDesign = StudyDesign.UNKNOWN
    sample_size: int | None = Field(default=None, ge=0)
    biological_replicates: int | None = Field(default=None, ge=0)
    technical_replicates: int | None = Field(default=None, ge=0)
    independent_replication_count: int | None = Field(default=None, ge=0)
    species: tuple[str, ...] = ()
    tissue: tuple[str, ...] = ()
    cell_type: tuple[str, ...] = ()
    patient_subtype: tuple[str, ...] = ()
    variant: tuple[str, ...] = ()
    protein_domain: tuple[str, ...] = ()
    disease_stage: tuple[str, ...] = ()
    age_context: str | None = None
    sex_context: str | None = None
    intervention: str | None = None
    comparator: str | None = None
    experimental_system: str | None = None
    assay: tuple[str, ...] = ()
    readout: tuple[str, ...] = ()
    direction: str | None = None
    statistical_result: str | None = None
    limitations: tuple[str, ...] = ()
    # Upstream curator fields kept verbatim; they are not our appraisal.
    curator_explanation: str | None = None
    upstream_directness: str | None = None
    model_fidelity: str | None = None
    evidence_extraction_confidence: float | None = Field(default=None, ge=0, le=1)
    human_review_status: HumanReviewStatus = HumanReviewStatus.UNREVIEWED
    retrieval_date: date
    provenance: Provenance

    @field_validator("pmid")
    @classmethod
    def normalize_pmid(cls, value: str | None) -> str | None:
        if value is None:
            return value
        match = PMID_RE.fullmatch(value.strip())
        if not match:
            raise ValueError("invalid PMID syntax")
        return f"PMID:{match.group(1)}"

    @field_validator("doi")
    @classmethod
    def normalize_doi(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if normalized.lower().startswith("https://doi.org/"):
            normalized = normalized[len("https://doi.org/") :]
        if normalized.lower().startswith("doi:"):
            normalized = normalized[len("doi:") :]
        if not DOI_RE.fullmatch(normalized):
            raise ValueError("invalid DOI syntax")
        return normalized.lower()

    @model_validator(mode="after")
    def require_reference_and_span(self) -> EvidenceItem:
        if not any((self.pmid, self.pmcid, self.doi, self.other_reference)):
            raise ValueError("at least one source identifier is required")
        if not self.exact_supported_span.strip():
            raise ValueError("exact_supported_span cannot be empty")
        return self


def split_reference(reference: str) -> dict[str, str]:
    """Map a DisMech reference CURIE into extended evidence identifier fields."""
    value = reference.strip()
    if PMID_RE.fullmatch(value):
        return {"pmid": value}
    if value.upper().startswith("PMCID:"):
        return {"pmcid": value.split(":", 1)[1]}
    if value.lower().startswith("doi:") or DOI_RE.fullmatch(value):
        return {"doi": value}
    return {"other_reference": value}


class CitationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    SPAN_NOT_LOCATED = "SPAN_NOT_LOCATED"
    TITLE_MISMATCH = "TITLE_MISMATCH"
    UNRESOLVED = "UNRESOLVED"
    NOT_CHECKABLE = "NOT_CHECKABLE"


class CitationVerification(BaseModel):
    """Deterministic check of an evidence pointer against retrieved source text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    identifier: str
    status: CitationStatus
    identifier_resolved: bool
    title_matches: bool | None
    span_location: str | None
    texts_checked: tuple[str, ...]
    source_snapshot_sha256: tuple[str, ...] = ()
    note: str


class ContextField(StrEnum):
    SPECIES = "species"
    TISSUE = "tissue"
    CELL_TYPE = "cell_type"
    VARIANT = "variant"
    PROTEIN_DOMAIN = "protein_domain"
    SUBTYPE = "subtype"
    EXPERIMENTAL_SYSTEM = "experimental_system"
    INTERVENTION = "intervention"
    ASSAY = "assay"
    READOUT = "readout"


class AnnotationBasis(StrEnum):
    STATED = "STATED"
    DERIVED = "DERIVED"
    NOT_STATED = "NOT_STATED"


class ContextAnnotation(BaseModel):
    """One context value with the verbatim text (or rule) that licenses it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: ContextField
    value: str
    basis: AnnotationBasis
    support_span: str | None = None
    source_location: str | None = None
    derivation: str | None = None

    @model_validator(mode="after")
    def basis_requires_support(self) -> ContextAnnotation:
        if self.basis is AnnotationBasis.STATED and not (
            self.support_span and self.source_location
        ):
            raise ValueError("STATED context requires a verbatim support span and location")
        if self.basis is AnnotationBasis.DERIVED and not self.derivation:
            raise ValueError("DERIVED context requires an explicit derivation rule")
        return self
