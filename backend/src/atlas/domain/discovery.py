"""Identity, web evidence, research-asset, and research-program records."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field, model_validator

from atlas.domain.reviews import ScientificReviewStatus


class OrganizationType(StrEnum):
    PATIENT_ORGANIZATION = "patient_organization"
    DISEASE_FOUNDATION = "disease_foundation"
    ACADEMIC_CENTER = "academic_center"
    HOSPITAL = "hospital"
    RESEARCH_INSTITUTE = "research_institute"
    BIOTECH = "biotech"
    PHARMA = "pharma"
    FUNDER = "funder"
    REPOSITORY = "repository"
    CONSORTIUM = "consortium"


class ProvenanceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_type: str
    source_id: str
    source_url: str | None = None
    snapshot_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    retrieved_at: datetime


class Researcher(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    researcher_id: str
    canonical_name: str
    aliases: tuple[str, ...] = ()
    orcid: str | None = None
    institution: str | None = None
    department: str | None = None
    laboratory: str | None = None
    country: str | None = None
    role: str | None = None
    email: str | None = None
    email_source: str | None = None
    official_profile_url: str | None = None
    publications: tuple[str, ...] = ()
    grants: tuple[str, ...] = ()
    trials: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    diseases: tuple[str, ...] = ()
    mechanisms: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()
    last_verified_at: datetime
    source_updated_at: datetime | None = None
    provenance: tuple[ProvenanceReference, ...]

    @model_validator(mode="after")
    def public_email_requires_source(self) -> Researcher:
        if self.email and not self.email_source:
            raise ValueError("professional email requires a verified public source")
        return self


class Laboratory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lab_id: str
    canonical_name: str
    institution: str
    pi_researcher_id: str | None = None
    # No verified official site may be assumed: a publication URL is provenance for an
    # author group, not evidence that a laboratory website was located and checked.
    official_url: str | None = None
    research_focus: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    diseases: tuple[str, ...] = ()
    mechanisms: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()
    personnel: tuple[str, ...] = ()
    grants: tuple[str, ...] = ()
    publications: tuple[str, ...] = ()
    last_verified_at: datetime
    source_updated_at: datetime | None = None
    provenance: tuple[ProvenanceReference, ...]


class Organization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: str
    canonical_name: str
    aliases: tuple[str, ...] = ()
    organization_type: OrganizationType
    country: str | None = None
    official_url: str
    disease_focus: tuple[str, ...] = ()
    mechanism_focus: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()
    patient_registry: str | None = None
    grants: tuple[str, ...] = ()
    programs: tuple[str, ...] = ()
    contact_source: str | None = None
    last_verified_at: datetime
    source_updated_at: datetime | None = None
    provenance: tuple[ProvenanceReference, ...]


class AssetType(StrEnum):
    REGISTRY = "registry"
    PATIENT_COHORT = "patient_cohort"
    NATURAL_HISTORY_DATASET = "natural_history_dataset"
    BIOBANK = "biobank"
    FIBROBLAST_LINE = "fibroblast_line"
    IPSC_LINE = "ipsc_line"
    NEURONAL_MODEL = "neuronal_model"
    ORGANOID = "organoid"
    CRISPR_LINE = "crispr_line"
    MOUSE_MODEL = "mouse_model"
    ZEBRAFISH_MODEL = "zebrafish_model"
    ASSAY = "assay"
    ANTIBODY = "antibody"
    PLASMID = "plasmid"
    BIOMARKER = "biomarker"
    PROTOCOL = "protocol"
    SEQUENCING_DATASET = "sequencing_dataset"
    PHENOTYPE_DATASET = "phenotype_dataset"
    CLINICAL_ENDPOINT = "clinical_endpoint"
    COMPOUND = "compound"
    THERAPEUTIC_PROGRAM = "therapeutic_program"


class AssetReuseStatus(StrEnum):
    VALIDATED_FOR_TARGET_CONTEXT = "VALIDATED_FOR_TARGET_CONTEXT"
    POTENTIALLY_REUSABLE = "POTENTIALLY_REUSABLE"
    REQUIRES_VALIDATION = "REQUIRES_VALIDATION"
    NOT_RELEVANT = "NOT_RELEVANT"
    UNKNOWN = "UNKNOWN"


class ResearchAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str
    canonical_name: str
    asset_type: AssetType
    owner: str | None = None
    organization: str | None = None
    creator: str | None = None
    disease_context: tuple[str, ...] = ()
    mechanism_context: tuple[str, ...] = ()
    variant_context: tuple[str, ...] = ()
    model_context: tuple[str, ...] = ()
    availability: str
    repository: str | None = None
    access_requirements: tuple[str, ...] = ()
    evidence: tuple[str, ...]
    source_url: str
    last_verified_at: datetime
    source_updated_at: datetime | None = None
    reuse_status: AssetReuseStatus = AssetReuseStatus.UNKNOWN
    human_review_status: ScientificReviewStatus = ScientificReviewStatus.PENDING

    @model_validator(mode="after")
    def validated_reuse_requires_target_evidence(self) -> ResearchAsset:
        if self.reuse_status is AssetReuseStatus.VALIDATED_FOR_TARGET_CONTEXT and not self.evidence:
            raise ValueError("validated reuse requires evidence in the target context")
        return self


class SourceQuality(StrEnum):
    STRUCTURED_AUTHORITATIVE = "STRUCTURED_AUTHORITATIVE"
    OFFICIAL_INSTITUTIONAL = "OFFICIAL_INSTITUTIONAL"
    OFFICIAL_ORGANIZATION = "OFFICIAL_ORGANIZATION"
    REPOSITORY = "REPOSITORY"
    GENERAL_WEB = "GENERAL_WEB"
    UNKNOWN = "UNKNOWN"


class ExtractionStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"


class WebEvidenceCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str
    title: str
    domain: str
    retrieved_at: datetime
    source_type: str
    organization: str | None = None
    person: str | None = None
    raw_text: str
    relevant_passages: tuple[str, ...]
    discovery_query: str
    extraction_status: ExtractionStatus
    source_quality: SourceQuality
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_reference: str

    @model_validator(mode="after")
    def content_hash_matches_text(self) -> WebEvidenceCandidate:
        if sha256(self.raw_text.encode()).hexdigest() != self.content_hash:
            raise ValueError("content_hash does not match raw_text")
        return self


class BrightDataUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str
    dataset: str
    endpoint: str
    pages_fetched: int = Field(ge=0)
    estimated_credits: float | None = Field(default=None, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    cached: bool
    snapshot_reference: str
    retrieved_at: datetime


class WebClaimStatus(StrEnum):
    EXTRACTED = "EXTRACTED"
    SUPPORTED = "SUPPORTED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class WebClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    subject: str
    predicate: str
    object: str
    exact_text: str
    source_url: str
    source_title: str
    source_type: str
    retrieval_date: date
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    extraction_method: str
    verification_status: WebClaimStatus = WebClaimStatus.EXTRACTED
    corroborating_sources: tuple[str, ...] = ()

    @model_validator(mode="after")
    def verified_web_claim_requires_corroboration(self) -> WebClaim:
        if self.verification_status is WebClaimStatus.VERIFIED and not (
            self.corroborating_sources
        ):
            raise ValueError("verified web claims require corroborating sources")
        return self


class Grant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    grant_id: str
    title: str
    principal_investigators: tuple[str, ...]
    organization: str
    abstract: str
    project_start: date | None = None
    project_end: date | None = None
    active: bool
    source_url: str
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ClinicalStudy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    study_id: str
    title: str
    overall_status: str
    investigators: tuple[str, ...] = ()
    organizations: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    interventions: tuple[str, ...] = ()
    source_url: str
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ResearchProgram(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    program_id: str
    organization: str
    disease: tuple[str, ...]
    gene: tuple[str, ...]
    mechanism: tuple[str, ...]
    therapeutic_modality: tuple[str, ...]
    development_stage: str
    assets: tuple[str, ...] = ()
    funding: tuple[str, ...] = ()
    geography: tuple[str, ...] = ()
    evidence: tuple[str, ...]
    current_status: str
    last_verified_at: datetime


class EntityResolutionStatus(StrEnum):
    MATCHED = "MATCHED"
    DISTINCT = "DISTINCT"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    UNRESOLVED = "UNRESOLVED"


class EntityResolutionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str
    left_entity_id: str
    right_entity_id: str
    status: EntityResolutionStatus
    matching_signals: tuple[str, ...] = ()
    conflicting_signals: tuple[str, ...] = ()
    rationale: str
    human_review_status: ScientificReviewStatus = ScientificReviewStatus.PENDING


class CapabilityEvidenceSignal(BaseModel):
    """A normalized observation used to verify, not merely extract, capability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    source_type: str
    subject_scope: str
    explicitly_demonstrates: bool
    biological_context_match: bool
    model_system_match: bool
    active: bool | None = None
    publication_year: int | None = Field(default=None, ge=1600, le=2200)
    exact_support: str
    source_url: str
