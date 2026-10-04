"""Field-level accounting for DisMech imports.

Every upstream field path must have a declared disposition: either it is
normalized into a typed internal field, or it is preserved verbatim (in an
object's provenance payload or a ``PreservedUpstreamRecord``) and documented as
not represented in typed form. A path with no declared disposition is reported
as ``UNDECLARED``: that is what "silently dropped" means here, and the audit
exists so that number can be checked to be zero.

Paths are normalized: list indices are replaced by ``[]``.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class FieldDisposition(StrEnum):
    STRUCTURAL = "structural"
    NORMALIZED = "normalized"
    PRESERVED_UNNORMALIZED = "preserved_unnormalized"
    UNDECLARED = "undeclared"


@dataclass(frozen=True, slots=True)
class FieldRule:
    disposition: FieldDisposition
    target: str
    subtree: bool = False


def _n(target: str, subtree: bool = False) -> FieldRule:
    return FieldRule(FieldDisposition.NORMALIZED, target, subtree)


def _p(target: str, subtree: bool = True) -> FieldRule:
    return FieldRule(FieldDisposition.PRESERVED_UNNORMALIZED, target, subtree)


_STRUCT = FieldRule(FieldDisposition.STRUCTURAL, "container")

NODE_PAYLOAD = "MechanismNode.provenance.source_payload"
PHENOTYPE_PAYLOAD = "Phenotype node provenance.source_payload"
EDGE_PAYLOAD = "MechanismEdge.provenance.source_payload"
EVIDENCE_PAYLOAD = "EvidenceItem.provenance.source_payload"

# Descriptor slots on pathophysiology nodes that become OntologyAnnotation rows.
NODE_DESCRIPTOR_SLOTS = (
    "assays",
    "biological_processes",
    "cell_types",
    "cellular_components",
    "chemical_entities",
    "gene",
    "gene_products",
    "genes",
    "locations",
    "molecular_functions",
    "pathways",
    "protein_complexes",
    "triggers",
)


def _evidence_rules(prefix: str) -> dict[str, FieldRule]:
    """Rules for an evidence list that the importer normalizes into EvidenceItem."""
    item = f"{prefix}[]"
    return {
        prefix: _STRUCT,
        item: _STRUCT,
        f"{item}.reference": _n("EvidenceItem.pmid|pmcid|doi|other_reference"),
        f"{item}.reference_title": _n("EvidenceItem.title"),
        f"{item}.snippet": _n("EvidenceItem.exact_supported_span"),
        f"{item}.supports": _n("EvidenceItem.evidence_relation"),
        f"{item}.quote_role": _n("EvidenceItem.evidence_origin + source_section"),
        f"{item}.evidence_source": _n("EvidenceItem.evidence_modality"),
        f"{item}.explanation": _n("EvidenceItem.curator_explanation"),
        f"{item}.directness": _n("EvidenceItem.upstream_directness"),
        f"{item}.images": _p(EVIDENCE_PAYLOAD),
    }


def _edge_rules(prefix: str, payload: str) -> dict[str, FieldRule]:
    item = f"{prefix}[]"
    return {
        prefix: _STRUCT,
        item: _STRUCT,
        f"{item}.target": _n("MechanismEdge.object_id (by node label)"),
        f"{item}.description": _n("Claim.original_statement"),
        f"{item}.causal_link_type": _n("MechanismEdge.causal_link_type"),
        f"{item}.hypothesis_groups": _n("MechanismEdge.hypothesis_groups"),
        f"{item}.intermediate_mechanisms": _n("MechanismEdge.intermediate_mechanisms"),
        **_evidence_rules(f"{item}.evidence"),
        # Any further edge attribute is kept verbatim in the edge payload.
        f"{item}.*": _p(payload),
    }


def _variant_rules(prefix: str, section: str) -> dict[str, FieldRule]:
    item = f"{prefix}[]"
    record = f"PreservedUpstreamRecord(section={section})"
    return {
        prefix: _STRUCT,
        item: _STRUCT,
        f"{item}.name": _n("Variant.upstream_label"),
        f"{item}.gene": _n("Variant.associated_gene", subtree=True),
        f"{item}.type": _n("Variant.variant_class"),
        f"{item}.variant_type": _n("Variant.variant_class"),
        f"{item}.clinical_significance": _n("Variant.clinical_significance"),
        f"{item}.*": _p(record),
    }


def _build_rules() -> dict[str, FieldRule]:
    rules: dict[str, FieldRule] = {
        "$": _STRUCT,
        # Disease identity.
        "$.name": _n("Disease.canonical_name"),
        "$.description": _n("Disease.description"),
        "$.disease_term": _n("Disease.mondo_id (disease_term.term.id)", subtree=True),
        "$.synonyms": _n("Disease.aliases"),
        "$.category": _n("Disease.disease_type"),
        "$.parents": _n("Disease.parents"),
        "$.updated_date": _n("Disease.source_date"),
        "$.creation_date": _n("Disease.source_date (fallback when updated_date absent)"),
        "$.mappings": _p("PreservedUpstreamRecord(section=mappings); MONDO used as fallback"),
        # Pathophysiology nodes.
        "$.pathophysiology": _STRUCT,
        "$.pathophysiology[]": _STRUCT,
        "$.pathophysiology[].name": _n("MechanismNode.label"),
        "$.pathophysiology[].description": _n("MechanismNode.description"),
        "$.pathophysiology[].biological_scale": _n(
            "MechanismNode.biological_scale + category"
        ),
        "$.pathophysiology[].mechanism_confidence": _n(
            "MechanismNode.upstream_mechanism_confidence"
        ),
        "$.pathophysiology[].role": _n("MechanismNode.upstream_role"),
        "$.pathophysiology[].subtypes": _n("Claim.subtype_context", subtree=True),
        **_evidence_rules("$.pathophysiology[].evidence"),
        **_edge_rules("$.pathophysiology[].downstream", EDGE_PAYLOAD),
        "$.pathophysiology[].*": _p(NODE_PAYLOAD),
        # Phenotypes.
        "$.phenotypes": _STRUCT,
        "$.phenotypes[]": _STRUCT,
        "$.phenotypes[].name": _n("Phenotype.label"),
        "$.phenotypes[].description": _n("MechanismNode.description"),
        "$.phenotypes[].phenotype_term": _STRUCT,
        "$.phenotypes[].phenotype_term.preferred_term": _n("Phenotype.label (cross-check)"),
        "$.phenotypes[].phenotype_term.term": _n("Phenotype.hpo_id", subtree=True),
        "$.phenotypes[].phenotype_term.*": _p(PHENOTYPE_PAYLOAD),
        "$.phenotypes[].frequency": _n("Phenotype.frequency"),
        "$.phenotypes[].severity": _n("Phenotype.severity"),
        "$.phenotypes[].context": _n("MechanismNode.context"),
        "$.phenotypes[].subtype": _n("Claim.subtype_context"),
        "$.phenotypes[].subtypes": _n("Claim.subtype_context", subtree=True),
        **_evidence_rules("$.phenotypes[].evidence"),
        **_edge_rules("$.phenotypes[].sequelae", EDGE_PAYLOAD),
        "$.phenotypes[].*": _p(PHENOTYPE_PAYLOAD),
        # Genetic associations: gene identity normalized, association context preserved.
        "$.genetic": _STRUCT,
        "$.genetic[]": _STRUCT,
        "$.genetic[].gene_term": _n("Gene.symbol + Gene.hgnc_id", subtree=True),
        "$.genetic[].name": _n("Gene.symbol (fallback)"),
        **_variant_rules("$.genetic[].variants", "genetic"),
        "$.genetic[].*": _p("PreservedUpstreamRecord(section=genetic)"),
        **_variant_rules("$.variants", "variants"),
        # Hypotheses.
        "$.mechanistic_hypotheses": _STRUCT,
        "$.mechanistic_hypotheses[]": _STRUCT,
        "$.mechanistic_hypotheses[].hypothesis_group_id": _n(
            "MechanisticHypothesis.hypothesis_id (hashed)"
        ),
        "$.mechanistic_hypotheses[].hypothesis_label": _n("MechanisticHypothesis.statement"),
        "$.mechanistic_hypotheses[].description": _n("MechanisticHypothesis.statement"),
        "$.mechanistic_hypotheses[].status": _n("MechanisticHypothesis.upstream_status"),
        "$.mechanistic_hypotheses[].applies_to_subtypes": _n(
            "MechanisticHypothesis.subtype_context"
        ),
        "$.mechanistic_hypotheses[].*": _p(
            "PreservedUpstreamRecord(section=mechanistic_hypotheses)"
        ),
        # Discussions: KNOWLEDGE_GAP becomes KnowledgeGap; every item is also preserved.
        "$.discussions": _STRUCT,
        "$.discussions[]": _STRUCT,
        "$.discussions[].discussion_id": _n("KnowledgeGap.gap_id (hashed)"),
        "$.discussions[].prompt": _n("KnowledgeGap.question"),
        "$.discussions[].kind": _n("KnowledgeGap selection (kind == KNOWLEDGE_GAP)"),
        "$.discussions[].rationale": _n("KnowledgeGap.why_it_matters"),
        "$.discussions[].attaches_to": _n("KnowledgeGap.related_edges"),
        "$.discussions[].status": _n("KnowledgeGap.status"),
        "$.discussions[].*": _p("PreservedUpstreamRecord(section=discussions)"),
    }
    for slot in NODE_DESCRIPTOR_SLOTS:
        rules[f"$.pathophysiology[].{slot}"] = _n(
            f"MechanismNode.annotations[slot={slot}]", subtree=True
        )
    return rules


RULES = _build_rules()

# Top-level sections not normalized in V1; each item becomes a PreservedUpstreamRecord.
PRESERVED_SECTIONS = (
    "agent_life_cycle",
    "animal_models",
    "biochemical",
    "categories",
    "classifications",
    "clinical_burden",
    "clinical_trials",
    "computational_models",
    "datasets",
    "definitions",
    "diagnosis",
    "differential_diagnoses",
    "environmental",
    "epidemiology",
    "experimental_models",
    "external_assertions",
    "gene_sets",
    "has_subtypes",
    "histopathology",
    "imaging_findings",
    "infectious_agent",
    "inheritance",
    "mappings",
    "modeling_considerations",
    "notes",
    "prevalence",
    "progression",
    "references",
    "review_notes",
    "stages",
    "tracked_issues",
    "transmission",
    "treatments",
)
for _section in PRESERVED_SECTIONS:
    RULES.setdefault(f"$.{_section}", _p(f"PreservedUpstreamRecord(section={_section})"))

# Top-level keys represented by the Disease object (and its provenance payload).
DISEASE_IDENTITY_KEYS = (
    "name",
    "description",
    "disease_term",
    "synonyms",
    "category",
    "parents",
    "updated_date",
    "creation_date",
)

_SEGMENT = re.compile(r"\.[^.\[]+|\[\]")


def normalize_path(path: str) -> str:
    return re.sub(r"\[\d+\]", "[]", path)


def resolve(path: str) -> tuple[FieldDisposition, str]:
    """Return the declared disposition for a normalized path."""
    exact = RULES.get(path)
    if exact is not None:
        return exact.disposition, exact.target
    segments = _SEGMENT.findall(path[1:])
    for cut in range(len(segments) - 1, 0, -1):
        prefix = "$" + "".join(segments[:cut])
        rule = RULES.get(prefix)
        if rule is not None and rule.subtree:
            return rule.disposition, rule.target
        # A wildcard covers an undeclared child subtree of its parent only. If the
        # child itself has a rule, unknown fields beneath it must stay UNDECLARED.
        wildcard = RULES.get(f"{prefix}.*")
        if wildcard is not None:
            child = prefix + segments[cut]
            if child == path or child not in RULES:
                return wildcard.disposition, wildcard.target
            break
    return FieldDisposition.UNDECLARED, "no declared disposition"


def observed_paths(document: Mapping[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()

    def walk(value: object, path: str) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                counts[child_path] += 1
                walk(child, child_path)
        elif isinstance(value, list):
            for child in value:
                walk(child, f"{path}[]")

    walk(document, "$")
    return counts


class FieldObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    occurrences: int
    disposition: FieldDisposition
    target: str


class ImportWarning(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    path: str
    message: str


class FieldAudit(BaseModel):
    """Machine-checkable statement of what happened to every upstream field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observations: tuple[FieldObservation, ...]
    undeclared_paths: tuple[str, ...]
    unretained_top_level_paths: tuple[str, ...]

    @property
    def silently_dropped_count(self) -> int:
        return len(self.undeclared_paths) + len(self.unretained_top_level_paths)

    def paths_with(self, disposition: FieldDisposition) -> tuple[FieldObservation, ...]:
        return tuple(item for item in self.observations if item.disposition is disposition)


def audit_fields(
    document: Mapping[str, Any], retained_object_paths: set[str]
) -> FieldAudit:
    """Classify every observed path and check top-level retention.

    ``retained_object_paths`` is the set of ``source_object_path`` values carried
    by the imported objects' provenance (nodes, phenotypes, preserved records).
    """
    observations = []
    for path, count in sorted(observed_paths(document).items()):
        disposition, target = resolve(path)
        observations.append(
            FieldObservation(path=path, occurrences=count, disposition=disposition, target=target)
        )
    undeclared = tuple(
        item.path for item in observations if item.disposition is FieldDisposition.UNDECLARED
    )
    unretained: list[str] = []
    for key, value in document.items():
        if key in DISEASE_IDENTITY_KEYS:
            continue
        if isinstance(value, list):
            for index in range(len(value)):
                path = f"{key}[{index}]"
                if path not in retained_object_paths:
                    unretained.append(path)
        elif key not in retained_object_paths:
            unretained.append(key)
    return FieldAudit(
        observations=tuple(observations),
        undeclared_paths=undeclared,
        unretained_top_level_paths=tuple(unretained),
    )
