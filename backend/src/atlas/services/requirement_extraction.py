"""Deterministically structure requirements already stated by an experiment."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from atlas.domain.action import (
    CapabilityCategory,
    RequiredAsset,
    RequiredAssetType,
    RequiredCapability,
    RequirementLevel,
)
from atlas.domain.experiments import ExperimentProposal


def _stable_id(prefix: str, experiment_id: str, value: str) -> str:
    return f"{prefix}:{uuid5(NAMESPACE_URL, f'{experiment_id}|{prefix}|{value.lower()}')}"


CAPABILITY_RULES: tuple[tuple[tuple[str, ...], CapabilityCategory, str], ...] = (
    (("ipsc", "maintenance"), CapabilityCategory.CELL_CULTURE, "iPSC maintenance"),
    (("crispr",), CapabilityCategory.CRISPR_EDITING, "STUB1 CRISPR editing"),
    (("knock-in",), CapabilityCategory.ISOGENIC_LINE_GENERATION, "isogenic line generation"),
    (
        ("differentiation", "neuronal"),
        CapabilityCategory.IPSC_NEURONAL_DIFFERENTIATION,
        "iPSC neuronal differentiation",
    ),
    (
        ("ubiquitinome",),
        CapabilityCategory.UBIQUITINATION_ASSAY,
        "quantitative ubiquitination analysis",
    ),
    (("digly",), CapabilityCategory.PROTEOMICS, "diGly enrichment proteomics"),
    (
        ("thermal stability",),
        CapabilityCategory.PROTEIN_BIOCHEMISTRY,
        "protein thermal-stability assay",
    ),
    (
        ("co-immunoprecipitation",),
        CapabilityCategory.PROTEIN_BIOCHEMISTRY,
        "co-immunoprecipitation",
    ),
    (
        ("statistical",),
        CapabilityCategory.STATISTICAL_ANALYSIS,
        "clone-aware statistical analysis",
    ),
)


ASSET_RULES: tuple[tuple[tuple[str, ...], RequiredAssetType], ...] = (
    (("patient-derived ipsc",), RequiredAssetType.PATIENT_DERIVED_IPSC),
    (("ipsc line",), RequiredAssetType.NEURONAL_MODEL),
    (("antibod",), RequiredAssetType.ANTIBODY),
    (("mass spectrometry",), RequiredAssetType.MASS_SPECTROMETRY_ACCESS),
    (("assay",), RequiredAssetType.ASSAY),
)


def _contains_all(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return all(term in lowered for term in terms)


def _extract_capabilities(experiment: ExperimentProposal) -> tuple[RequiredCapability, ...]:
    found: list[RequiredCapability] = []
    seen: set[CapabilityCategory] = set()
    for index, phrase in enumerate(experiment.required_capabilities):
        matches = [rule for rule in CAPABILITY_RULES if _contains_all(phrase, rule[0])]
        if not matches:
            matches = [((phrase.lower(),), CapabilityCategory.OTHER, phrase)]
        for _, category, name in matches:
            if category in seen:
                continue
            seen.add(category)
            found.append(
                RequiredCapability(
                    capability_id=_stable_id("required-capability", experiment.experiment_id, name),
                    experiment_id=experiment.experiment_id,
                    canonical_name=name,
                    description=phrase,
                    capability_category=category,
                    required_or_optional=RequirementLevel.REQUIRED,
                    reason_required=f"The experiment explicitly requires: {phrase}",
                    mechanism_context=experiment.hypothesis,
                    disease_context=experiment.scientific_question,
                    model_context=experiment.model_system,
                    evidence_source=(
                        f"{experiment.experiment_id}#required_capabilities[{index}]"
                    ),
                    generated_by="deterministic-requirement-extractor:v1",
                )
            )
    return tuple(found)


def _first_asset_type(phrase: str) -> RequiredAssetType:
    for terms, asset_type in ASSET_RULES:
        if _contains_all(phrase, terms):
            return asset_type
    return RequiredAssetType.OTHER


def _extract_assets(experiment: ExperimentProposal) -> tuple[RequiredAsset, ...]:
    result: list[RequiredAsset] = []
    variant_context = "; ".join(experiment.patient_stratification)
    for index, phrase in enumerate(experiment.required_assets):
        result.append(
            RequiredAsset(
                required_asset_id=_stable_id("required-asset", experiment.experiment_id, phrase),
                experiment_id=experiment.experiment_id,
                asset_type=_first_asset_type(phrase),
                description=phrase,
                required_characteristics=(phrase,),
                biological_context=experiment.scientific_question,
                variant_context=variant_context,
                model_context=experiment.model_system,
                reason_required=f"The experiment explicitly lists this required asset: {phrase}",
                evidence_source=f"{experiment.experiment_id}#required_assets[{index}]",
            )
        )
    return tuple(result)


def extract_experiment_requirements(
    experiment: ExperimentProposal,
) -> tuple[tuple[RequiredCapability, ...], tuple[RequiredAsset, ...]]:
    """Convert explicit proposal strings to reviewed, typed requirements."""
    return _extract_capabilities(experiment), _extract_assets(experiment)
