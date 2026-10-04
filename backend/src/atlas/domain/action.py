"""Experiment-driven requirements and evidence-qualified collaboration models."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from atlas.domain.reviews import ScientificReviewStatus


class CapabilityCategory(StrEnum):
    CELL_CULTURE = "cell_culture"
    PATIENT_DERIVED_CELL_HANDLING = "patient_derived_cell_handling"
    IPSC_GENERATION = "ipsc_generation"
    IPSC_NEURONAL_DIFFERENTIATION = "ipsc_neuronal_differentiation"
    CRISPR_EDITING = "crispr_editing"
    ISOGENIC_LINE_GENERATION = "isogenic_line_generation"
    VARIANT_ENGINEERING = "variant_engineering"
    PROTEIN_BIOCHEMISTRY = "protein_biochemistry"
    UBIQUITINATION_ASSAY = "ubiquitination_assay"
    ENZYMATIC_ASSAY = "enzymatic_assay"
    PROTEOSTASIS_ASSAY = "proteostasis_assay"
    PROTEOMICS = "proteomics"
    TRANSCRIPTOMICS = "transcriptomics"
    SINGLE_CELL_SEQUENCING = "single_cell_sequencing"
    IMAGING = "imaging"
    ELECTROPHYSIOLOGY = "electrophysiology"
    ANIMAL_MODEL = "animal_model"
    MOUSE_GENETICS = "mouse_genetics"
    ZEBRAFISH = "zebrafish"
    PATHOLOGY = "pathology"
    BIOMARKER_ANALYSIS = "biomarker_analysis"
    NATURAL_HISTORY = "natural_history"
    PATIENT_RECRUITMENT = "patient_recruitment"
    REGISTRY_MANAGEMENT = "registry_management"
    CLINICAL_PHENOTYPING = "clinical_phenotyping"
    THERAPEUTIC_DEVELOPMENT = "therapeutic_development"
    GENE_THERAPY = "gene_therapy"
    AAV = "aav"
    ASO = "aso"
    RNAI = "rnai"
    SMALL_MOLECULE_SCREENING = "small_molecule_screening"
    CLINICAL_TRIAL_DESIGN = "clinical_trial_design"
    REGULATORY_EXPERTISE = "regulatory_expertise"
    STATISTICAL_ANALYSIS = "statistical_analysis"
    OTHER = "other"


class RequirementLevel(StrEnum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"


class RequiredCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_id: str
    experiment_id: str
    canonical_name: str
    description: str
    capability_category: CapabilityCategory
    required_or_optional: RequirementLevel
    reason_required: str
    mechanism_context: str
    disease_context: str
    model_context: str
    evidence_source: str
    generated_by: str
    human_review_status: ScientificReviewStatus = ScientificReviewStatus.PENDING


class RequiredAssetType(StrEnum):
    PATIENT_COHORT = "patient_cohort"
    REGISTRY = "registry"
    NATURAL_HISTORY_DATASET = "natural_history_dataset"
    PATIENT_DERIVED_FIBROBLASTS = "patient_derived_fibroblasts"
    PATIENT_DERIVED_IPSC = "patient_derived_ipsc"
    ISOGENIC_CONTROL = "isogenic_control"
    CRISPR_LINE = "crispr_line"
    NEURONAL_MODEL = "neuronal_model"
    ANIMAL_MODEL = "animal_model"
    ASSAY = "assay"
    ANTIBODY = "antibody"
    PLASMID = "plasmid"
    PROTOCOL = "protocol"
    SEQUENCING_DATASET = "sequencing_dataset"
    PHENOTYPE_DATASET = "phenotype_dataset"
    BIOMARKER_ASSAY = "biomarker_assay"
    TISSUE_SAMPLE = "tissue_sample"
    BIOBANK = "biobank"
    CLINICAL_OUTCOME_MEASURE = "clinical_outcome_measure"
    COMPUTATIONAL_PIPELINE = "computational_pipeline"
    MASS_SPECTROMETRY_ACCESS = "mass_spectrometry_access"
    OTHER = "other"


class RequiredAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    required_asset_id: str
    experiment_id: str
    asset_type: RequiredAssetType
    description: str
    required_characteristics: tuple[str, ...]
    biological_context: str
    variant_context: str
    model_context: str
    reason_required: str
    alternatives: tuple[str, ...] = ()
    evidence_source: str
    human_review_status: ScientificReviewStatus = ScientificReviewStatus.PENDING


class CapabilityClaimStatus(StrEnum):
    VERIFIED = "VERIFIED"
    SUPPORTED = "SUPPORTED"
    PLAUSIBLE = "PLAUSIBLE"
    UNVERIFIED = "UNVERIFIED"
    CONTRADICTED = "CONTRADICTED"
    OUTDATED = "OUTDATED"


class CapabilityDirectness(StrEnum):
    DIRECT = "DIRECT"
    TEAM_LEVEL = "TEAM_LEVEL"
    INSTITUTION_LEVEL = "INSTITUTION_LEVEL"
    INDIRECT = "INDIRECT"


class CapabilityClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    subject_type: str
    subject_id: str
    capability_id: str
    statement: str
    evidence_items: tuple[str, ...]
    evidence_source_types: tuple[str, ...]
    directness: CapabilityDirectness
    recency: str
    corroboration_count: int = Field(ge=0)
    status: CapabilityClaimStatus
    rationale: str
    last_checked: date
    human_review_status: ScientificReviewStatus = ScientificReviewStatus.PENDING

    @model_validator(mode="after")
    def verified_claims_need_strong_evidence(self) -> CapabilityClaim:
        if self.status is CapabilityClaimStatus.VERIFIED:
            if self.corroboration_count < 2 or len(set(self.evidence_source_types)) < 2:
                raise ValueError("VERIFIED capability requires two sources of different types")
            if self.directness is CapabilityDirectness.INSTITUTION_LEVEL:
                raise ValueError("institution infrastructure cannot verify a personal capability")
        return self


class MatchLevel(StrEnum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class MatchDimensions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mechanism_match: MatchLevel
    gene_match: MatchLevel
    disease_match: MatchLevel
    model_system_match: MatchLevel
    experimental_method_match: MatchLevel
    asset_match: MatchLevel
    active_funding: MatchLevel
    publication_recency: MatchLevel
    capability_evidence_quality: MatchLevel
    geographic_relevance: MatchLevel


class ActionabilityStatus(StrEnum):
    READY_FOR_EXPERT_REVIEW = "READY_FOR_EXPERT_REVIEW"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"
    MISSING_ASSET = "MISSING_ASSET"
    MISSING_CAPABILITY = "MISSING_CAPABILITY"
    CONTACT_UNVERIFIED = "CONTACT_UNVERIFIED"
    DUPLICATION_RISK = "DUPLICATION_RISK"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    BLOCKED = "BLOCKED"


class CollaborationParticipant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_type: str
    subject_id: str
    proposed_role: str
    capability_claim_ids: tuple[str, ...] = ()
    asset_ids: tuple[str, ...] = ()


class CollaborationOpportunity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    collaboration_id: str
    experiment_id: str
    knowledge_gap_id: str
    participants: tuple[CollaborationParticipant, ...]
    provided_capabilities: tuple[str, ...]
    provided_assets: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    rationale: str
    evidence: tuple[str, ...]
    uncertainties: tuple[str, ...]
    duplication_risk: str
    synergy: str
    proposed_roles: tuple[str, ...]
    first_contact_target: str | None
    suggested_next_action: str
    status: ActionabilityStatus
    human_review_status: ScientificReviewStatus = ScientificReviewStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def recommendation_requires_evidence(self) -> CollaborationOpportunity:
        if self.status is ActionabilityStatus.READY_FOR_EXPERT_REVIEW and (
            not self.evidence or not self.participants
        ):
            raise ValueError("review-ready collaborations require participants and evidence")
        return self
