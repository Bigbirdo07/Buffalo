"""Mechanism graph records with explicit causal restraint."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from atlas.domain.claims import RefinementStatus
from atlas.domain.provenance import Provenance, ProvenanceKind


class MechanismNodeCategory(StrEnum):
    MOLECULAR_EVENT = "molecular_event"
    GENE_FUNCTION = "gene_function"
    PROTEIN_FUNCTION = "protein_function"
    PROTEIN_COMPLEX = "protein_complex"
    PATHWAY = "pathway"
    CELLULAR_PROCESS = "cellular_process"
    CELL_STATE = "cell_state"
    TISSUE_PROCESS = "tissue_process"
    PHYSIOLOGICAL_PROCESS = "physiological_process"
    PHENOTYPE = "phenotype"
    UNSPECIFIED = "unspecified"


class OntologyAnnotation(BaseModel):
    """One upstream descriptor (GO/CL/UBERON/HGNC/CHEBI/...) attached to a node."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    slot: str
    preferred_term: str | None = None
    term_id: str | None = None
    term_label: str | None = None
    modifier: str | None = None


class MechanismNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    label: str
    category: MechanismNodeCategory
    description: str | None = None
    biological_scale: str | None = None
    context: tuple[str, ...] = ()
    annotations: tuple[OntologyAnnotation, ...] = ()
    upstream_mechanism_confidence: str | None = None
    upstream_role: str | None = None
    evidence_ids: tuple[str, ...] = ()
    source_kind: ProvenanceKind
    provenance: Provenance


class MechanismEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    subject_id: str
    predicate: str
    object_id: str
    causal_direction: str = "FORWARD"
    claim_id: str
    status: RefinementStatus = RefinementStatus.UNREVIEWED
    contexts: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    hypothesis_groups: tuple[str, ...] = ()
    causal_link_type: str | None = None
    intermediate_mechanisms: tuple[str, ...] = ()
    source_kind: ProvenanceKind
    provenance: Provenance


class MechanismGraph(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    disease_id: str
    nodes: tuple[MechanismNode, ...]
    edges: tuple[MechanismEdge, ...]

