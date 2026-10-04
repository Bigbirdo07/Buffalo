"""Read-only adapter for the current DisMech disorder YAML/JSON shape.

The boundary is intentionally tolerant of additive upstream schema evolution,
but it never discards silently: every upstream field path receives a declared
disposition in :mod:`atlas.adapters.dismech.field_audit`, and every top-level
item is retained verbatim in a provenance payload or a ``PreservedUpstreamRecord``.
The normalized scientific objects on our side remain strict.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict

from atlas.adapters.dismech.field_audit import (
    DISEASE_IDENTITY_KEYS,
    NODE_DESCRIPTOR_SLOTS,
    PRESERVED_SECTIONS,
    FieldAudit,
    ImportWarning,
    audit_fields,
)
from atlas.domain.claims import Claim, ClaimType
from atlas.domain.entities import Disease, Gene, Phenotype, Variant
from atlas.domain.evidence import (
    EvidenceItem,
    EvidenceModality,
    EvidenceOrigin,
    EvidenceRelation,
    SourceSection,
    StudyDesign,
    split_reference,
)
from atlas.domain.experiments import HypothesisStatus, MechanisticHypothesis
from atlas.domain.gaps import (
    GapPriorityDimensions,
    GapType,
    KnowledgeGap,
    pending_search_coverage,
)
from atlas.domain.mechanism import (
    MechanismEdge,
    MechanismGraph,
    MechanismNode,
    MechanismNodeCategory,
    OntologyAnnotation,
)
from atlas.domain.provenance import Provenance, ProvenanceKind, SourceSnapshot
from atlas.graph.algorithms import longest_causal_chain

# Sections normalized (partly or fully) whose items are *also* kept as records,
# because some of their fields are not represented in typed form.
PARTIALLY_NORMALIZED_SECTIONS = ("genetic", "variants", "mechanistic_hypotheses", "discussions")

DISCUSSION_QUALIFYING_KINDS = frozenset(
    {"CONTROVERSY", "HUMAN_MODEL_MISMATCH", "OPEN_QUESTION", "INTERPRETATION"}
)


def _stable_id(namespace: str, *parts: str) -> str:
    value = "|".join((namespace, *parts))
    return str(uuid5(NAMESPACE_URL, value))


def _as_sequence(value: object) -> Sequence[object]:
    if value is None:
        return ()
    if isinstance(value, list | tuple):
        return value
    return (value,)


def _strings(value: object) -> tuple[str, ...]:
    result: list[str] = []
    for item in _as_sequence(value):
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, Mapping):
            candidate = item.get("preferred_term") or item.get("name") or item.get("id")
            if candidate:
                result.append(str(candidate))
    return tuple(result)


def _normalize_curie(value: str) -> str:
    """Upper-case the prefix of the CURIE prefixes DisMech emits in lower case."""
    prefix, _, local = value.partition(":")
    if prefix.lower() in {"hgnc", "mondo", "hp", "go", "cl", "uberon", "chebi", "ncbitaxon"}:
        return f"{prefix.upper()}:{local}"
    return value


def _descriptor_id(value: object) -> str | None:
    """Return the ontology CURIE of a DisMech descriptor (``term: {id, label}``)."""
    if isinstance(value, str) and ":" in value:
        return _normalize_curie(value)
    if isinstance(value, Mapping):
        term = value.get("term")
        if isinstance(term, Mapping):
            candidate = term.get("id")
            if isinstance(candidate, str) and ":" in candidate:
                return _normalize_curie(candidate)
        for key in ("id", "term", "identifier"):
            candidate = value.get(key)
            if isinstance(candidate, str) and ":" in candidate:
                return _normalize_curie(candidate)
    return None


def _descriptor_label(value: object) -> str | None:
    if isinstance(value, Mapping):
        term = value.get("term")
        if isinstance(term, Mapping) and isinstance(term.get("label"), str):
            return str(term["label"])
    return None


def _payload_hash(payload: object) -> str:
    return sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class CandidateMetrics(BaseModel):
    """Visible demo-selection dimensions; deliberately no opaque total score."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pathophysiology_nodes: int
    causal_edges: int
    longest_causal_chain: int = 0
    evidence_items: int
    edges_without_evidence: int = 0
    refute_or_no_evidence_items: int = 0
    provisional_or_hypothetical_nodes: int = 0
    alternative_or_emerging_hypotheses: int = 0
    genes: int
    variants: int
    variants_with_functional_effects: int = 0
    protein_domain_mentions: int = 0
    phenotypes: int
    subtypes: int
    experimental_models: int
    animal_models: int = 0
    model_organism_evidence_items: int = 0
    explicit_gaps_or_controversies: int
    human_model_mismatch_discussions: int = 0
    upstream_proposed_experiments: int = 0
    clinical_trials: int = 0
    datasets: int = 0
    references: int = 0


class PreservedUpstreamRecord(BaseModel):
    """A verbatim upstream object that is not (fully) normalized into typed fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str
    section: str
    reason: str
    payload_sha256: str
    provenance: Provenance


class ImportedDisease(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot: SourceSnapshot
    disease: Disease
    genes: tuple[Gene, ...]
    variants: tuple[Variant, ...]
    phenotypes: tuple[Phenotype, ...]
    claims: tuple[Claim, ...]
    evidence: tuple[EvidenceItem, ...]
    graph: MechanismGraph
    hypotheses: tuple[MechanisticHypothesis, ...]
    imported_gaps: tuple[KnowledgeGap, ...]
    preserved_records: tuple[PreservedUpstreamRecord, ...] = ()
    warnings: tuple[ImportWarning, ...] = ()
    field_audit: FieldAudit
    candidate_metrics: CandidateMetrics


class DisMechImportError(ValueError):
    """A path-specific boundary failure in an upstream DisMech document."""


class DisMechImporter:
    """Normalize a DisMech disorder document without mutating source content."""

    def __init__(self, *, source_version: str, retrieval_date: date | None = None) -> None:
        if not source_version.strip():
            raise ValueError("source_version (preferably a DisMech commit) is required")
        self.source_version = source_version
        self.retrieval_date = retrieval_date or date.today()
        self._warnings: list[ImportWarning] = []

    @staticmethod
    def stable_locator(path: Path) -> str:
        """A cwd-independent locator for a source file.

        Deterministic identities must not depend on how the file was addressed, so
        the locator is the path from the upstream ``kb/disorders`` directory onward
        when present, and otherwise the bare filename. Importing the same file by
        relative or absolute path therefore yields the same IDs.
        """
        parts = path.resolve().parts
        for index in range(len(parts) - 1):
            if parts[index] == "kb" and parts[index + 1] == "disorders":
                return "/".join(parts[index:])
        return path.name

    def load_path(self, path: Path, *, source_locator: str | None = None) -> ImportedDisease:
        raw = path.read_bytes()
        suffix = path.suffix.lower()
        if suffix == ".json":
            document = json.loads(raw)
            media_type = "application/json"
        elif suffix in {".yaml", ".yml"}:
            try:
                import yaml
            except ImportError as exc:  # pragma: no cover - environment-specific
                raise DisMechImportError(
                    "PyYAML is required for YAML imports; install the backend dependencies"
                ) from exc
            document = yaml.safe_load(raw)
            media_type = "application/yaml"
        else:
            raise DisMechImportError(f"unsupported source format: {suffix}")
        if not isinstance(document, Mapping):
            raise DisMechImportError("DisMech document root must be an object")
        return self.import_document(
            document,
            source_locator=source_locator or self.stable_locator(path),
            raw_content=raw,
            media_type=media_type,
        )

    def import_document(
        self,
        document: Mapping[str, Any],
        *,
        source_locator: str,
        raw_content: bytes | None = None,
        media_type: str = "application/json",
    ) -> ImportedDisease:
        self._warnings = []
        name = document.get("name")
        if not isinstance(name, str) or not name.strip():
            raise DisMechImportError("name: required non-empty disease name")
        canonical = json.dumps(document, sort_keys=True, ensure_ascii=False, default=str).encode()
        snapshot = SourceSnapshot.from_bytes(
            source_name="DisMech",
            source_locator=source_locator,
            source_version=self.source_version,
            media_type=media_type,
            content=raw_content if raw_content is not None else canonical,
        )
        disease = self._import_disease(document, name, source_locator, snapshot)
        disease_id = disease.id

        claims: list[Claim] = []
        evidence: list[EvidenceItem] = []
        nodes: list[MechanismNode] = []
        edges: list[MechanismEdge] = []
        node_by_label: dict[str, MechanismNode] = {}

        pathophysiology = self._mapping_list(document, "pathophysiology")
        phenotypes_raw = self._mapping_list(document, "phenotypes")

        for index, raw_node in enumerate(pathophysiology):
            path = f"pathophysiology[{index}]"
            label = self._required_text(raw_node, "name", path)
            node_id = _stable_id("dismech:node", disease_id, path, label)
            node_claim_id = _stable_id("dismech:claim", disease_id, path, label)
            node_evidence = self._import_evidence(
                raw_node.get("evidence"), node_claim_id, snapshot, f"{path}.evidence"
            )
            evidence.extend(node_evidence)
            provenance = self._provenance(snapshot, path, dict(raw_node))
            annotations = self._node_annotations(raw_node)
            node = MechanismNode(
                id=node_id,
                label=label,
                category=self._node_category(raw_node),
                description=self._optional_text(raw_node.get("description")),
                biological_scale=self._optional_text(raw_node.get("biological_scale")),
                context=self._node_context(raw_node),
                annotations=annotations,
                upstream_mechanism_confidence=self._optional_text(
                    raw_node.get("mechanism_confidence")
                ),
                upstream_role=self._optional_text(raw_node.get("role")),
                evidence_ids=tuple(item.evidence_id for item in node_evidence),
                source_kind=ProvenanceKind.CURATED,
                provenance=provenance,
            )
            if label in node_by_label:
                raise DisMechImportError(f"{path}.name: duplicate pathograph label {label!r}")
            node_by_label[label] = node
            nodes.append(node)
            claims.append(
                Claim(
                    claim_id=node_claim_id,
                    subject=name,
                    predicate="HAS_MECHANISM_COMPONENT",
                    object=label,
                    normalized_statement=f"{label} is represented in the mechanism for {name}.",
                    original_statement=self._optional_text(raw_node.get("description")) or label,
                    claim_scope="Imported node-level curated assertion",
                    claim_type=ClaimType.CURATED,
                    disease_context=disease_id,
                    subtype_context=_strings(raw_node.get("subtypes")),
                    species=("Homo sapiens",),
                    tissue=self._annotation_labels(annotations, "locations"),
                    cell_type=self._annotation_labels(annotations, "cell_types"),
                    experimental_context=_strings(raw_node.get("assays")),
                    source_claim_origin=path,
                    extraction_method="deterministic_dismech_node_import",
                    provenance=provenance,
                )
            )

        phenotypes: list[Phenotype] = []
        for index, raw_phenotype in enumerate(phenotypes_raw):
            path = f"phenotypes[{index}]"
            label = self._required_text(raw_phenotype, "name", path)
            phenotype_id = _stable_id("dismech:phenotype", disease_id, path, label)
            claim_id = _stable_id("dismech:claim", disease_id, path, label)
            phenotype_evidence = self._import_evidence(
                raw_phenotype.get("evidence"), claim_id, snapshot, f"{path}.evidence"
            )
            evidence.extend(phenotype_evidence)
            hpo = _descriptor_id(raw_phenotype.get("phenotype_term"))
            if hpo is not None and not hpo.startswith("HP:"):
                self._warn(
                    "NON_HPO_PHENOTYPE_TERM",
                    f"{path}.phenotype_term",
                    f"Phenotype term {hpo!r} is not an HPO CURIE; hpo_id left empty.",
                )
                hpo = None
            phenotypes.append(
                Phenotype(
                    id=phenotype_id,
                    hpo_id=hpo,
                    label=label,
                    frequency=self._optional_text(raw_phenotype.get("frequency")),
                    onset=self._optional_text(raw_phenotype.get("onset")),
                    severity=self._optional_text(raw_phenotype.get("severity")),
                    source="DisMech",
                    evidence_ids=tuple(item.evidence_id for item in phenotype_evidence),
                )
            )
            provenance = self._provenance(snapshot, path, dict(raw_phenotype))
            phenotype_node = MechanismNode(
                id=phenotype_id,
                label=label,
                category=MechanismNodeCategory.PHENOTYPE,
                description=self._optional_text(raw_phenotype.get("description")),
                context=_strings(raw_phenotype.get("context")),
                evidence_ids=tuple(item.evidence_id for item in phenotype_evidence),
                source_kind=ProvenanceKind.CURATED,
                provenance=provenance,
            )
            if label in node_by_label:
                self._warn(
                    "PHENOTYPE_LABEL_SHADOWED",
                    f"{path}.name",
                    f"Phenotype {label!r} shares a label with an earlier node; edges that "
                    "target this label resolve to the earlier node.",
                )
            node_by_label.setdefault(label, phenotype_node)
            nodes.append(phenotype_node)
            claims.append(
                Claim(
                    claim_id=claim_id,
                    subject=name,
                    predicate="HAS_PHENOTYPE",
                    object=label,
                    normalized_statement=f"{name} is associated with phenotype {label}.",
                    original_statement=(
                        self._optional_text(raw_phenotype.get("description")) or label
                    ),
                    claim_scope="Imported phenotype association",
                    claim_type=ClaimType.CURATED,
                    disease_context=disease_id,
                    subtype_context=(
                        *_strings(raw_phenotype.get("subtype")),
                        *_strings(raw_phenotype.get("subtypes")),
                    ),
                    species=("Homo sapiens",),
                    source_claim_origin=path,
                    extraction_method="deterministic_dismech_phenotype_import",
                    provenance=provenance,
                )
            )

        # Causal edges: pathophysiology downstream links and phenotype sequelae.
        edge_sources: list[tuple[str, Mapping[str, Any], str]] = [
            (f"pathophysiology[{index}]", raw, "downstream")
            for index, raw in enumerate(pathophysiology)
        ] + [(f"phenotypes[{index}]", raw, "sequelae") for index, raw in enumerate(phenotypes_raw)]
        source_node_by_path = {node.provenance.source_object_path: node for node in nodes}
        for parent_path, raw_parent, slot in edge_sources:
            source_node = source_node_by_path[parent_path]
            for edge_index, raw_edge in enumerate(
                self._mapping_list(raw_parent, slot, parent=parent_path)
            ):
                path = f"{parent_path}.{slot}[{edge_index}]"
                target_label = self._required_text(raw_edge, "target", path)
                if target_label not in node_by_label:
                    self._warn(
                        "DANGLING_EDGE_TARGET",
                        f"{path}.target",
                        f"Edge target {target_label!r} matches no pathophysiology or "
                        "phenotype name; an UNSPECIFIED referenced node was created.",
                    )
                    target = self._referenced_target(
                        disease_id, target_label, snapshot, f"{path}.target"
                    )
                    node_by_label[target_label] = target
                    nodes.append(target)
                target_node = node_by_label[target_label]
                claim_id = _stable_id(
                    "dismech:claim", disease_id, path, source_node.label, target_label
                )
                edge_evidence = self._import_evidence(
                    raw_edge.get("evidence"), claim_id, snapshot, f"{path}.evidence"
                )
                evidence.extend(edge_evidence)
                provenance = self._provenance(snapshot, path, dict(raw_edge))
                original = self._optional_text(raw_edge.get("description")) or (
                    f"{source_node.label} leads {slot} to {target_label}"
                )
                claim = Claim(
                    claim_id=claim_id,
                    subject=source_node.id,
                    predicate="CAUSES_OR_CONTRIBUTES_TO",
                    object=target_node.id,
                    normalized_statement=f"{source_node.label} contributes to {target_label}.",
                    original_statement=original,
                    claim_scope=f"Imported explicit DisMech {slot} edge",
                    claim_type=ClaimType.CURATED,
                    disease_context=disease_id,
                    subtype_context=_strings(raw_parent.get("subtypes")),
                    species=("Homo sapiens",),
                    tissue=self._annotation_labels(source_node.annotations, "locations"),
                    cell_type=self._annotation_labels(source_node.annotations, "cell_types"),
                    source_claim_origin=path,
                    extraction_method="deterministic_dismech_edge_import",
                    provenance=provenance,
                )
                claims.append(claim)
                edges.append(
                    MechanismEdge(
                        id=_stable_id("dismech:edge", disease_id, path, claim_id),
                        subject_id=source_node.id,
                        predicate="CAUSES_OR_CONTRIBUTES_TO",
                        object_id=target_node.id,
                        claim_id=claim_id,
                        contexts=source_node.context,
                        evidence_ids=tuple(item.evidence_id for item in edge_evidence),
                        hypothesis_groups=_strings(raw_edge.get("hypothesis_groups")),
                        causal_link_type=self._optional_text(raw_edge.get("causal_link_type")),
                        intermediate_mechanisms=_strings(raw_edge.get("intermediate_mechanisms")),
                        source_kind=ProvenanceKind.CURATED,
                        provenance=provenance,
                    )
                )

        graph = MechanismGraph(disease_id=disease_id, nodes=tuple(nodes), edges=tuple(edges))
        genes = self._import_genes(document, disease_id)
        variants = self._import_variants(document, disease_id)
        hypotheses = self._import_hypotheses(document, disease_id)
        gaps = self._import_discussion_gaps(document, disease_id)
        records = self._preserve_records(document, disease_id, snapshot)
        retained = {node.provenance.source_object_path for node in nodes}
        retained.update(record.provenance.source_object_path for record in records)
        audit = audit_fields(document, retained)
        metrics = self.candidate_metrics(document, graph, evidence)
        return ImportedDisease(
            snapshot=snapshot,
            disease=disease,
            genes=genes,
            variants=variants,
            phenotypes=tuple(phenotypes),
            claims=tuple(claims),
            evidence=tuple(evidence),
            graph=graph,
            hypotheses=hypotheses,
            imported_gaps=gaps,
            preserved_records=records,
            warnings=tuple(self._warnings),
            field_audit=audit,
            candidate_metrics=metrics,
        )

    def candidate_metrics(
        self,
        document: Mapping[str, Any],
        graph: MechanismGraph,
        evidence: Sequence[EvidenceItem],
    ) -> CandidateMetrics:
        paths = self._mapping_list(document, "pathophysiology")
        discussions = self._mapping_list(document, "discussions")
        genetic = self._mapping_list(document, "genetic")
        all_variants = list(self._mapping_list(document, "variants"))
        for gene in genetic:
            all_variants.extend(self._mapping_list(gene, "variants"))
        kinds = [str(item.get("kind", "")).upper() for item in discussions]

        polarity_counts = {"REFUTE": 0, "NO_EVIDENCE": 0, "MODEL_ORGANISM": 0}

        def walk(value: object) -> None:
            if isinstance(value, Mapping):
                if "reference" in value and "supports" in value:
                    supports = str(value.get("supports")).upper()
                    if supports in polarity_counts:
                        polarity_counts[supports] += 1
                    if str(value.get("evidence_source")).upper() == "MODEL_ORGANISM":
                        polarity_counts["MODEL_ORGANISM"] += 1
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(document)
        domain_mentions = sum(
            1
            for item in [*paths, *all_variants]
            if "domain" in json.dumps(item, default=str).lower()
        )
        return CandidateMetrics(
            pathophysiology_nodes=len(paths),
            causal_edges=len(graph.edges),
            longest_causal_chain=longest_causal_chain(graph),
            evidence_items=len(evidence),
            edges_without_evidence=sum(1 for edge in graph.edges if not edge.evidence_ids),
            refute_or_no_evidence_items=polarity_counts["REFUTE"] + polarity_counts["NO_EVIDENCE"],
            provisional_or_hypothetical_nodes=sum(
                1
                for node in paths
                if str(node.get("mechanism_confidence", "")).upper()
                in {"PROVISIONAL", "HYPOTHETICAL"}
            ),
            alternative_or_emerging_hypotheses=sum(
                1
                for item in self._mapping_list(document, "mechanistic_hypotheses")
                if str(item.get("status", "")).upper() in {"ALTERNATIVE", "EMERGING"}
            ),
            genes=len(genetic),
            variants=len(all_variants),
            variants_with_functional_effects=sum(
                1 for item in all_variants if item.get("functional_effects")
            ),
            protein_domain_mentions=domain_mentions,
            phenotypes=len(self._mapping_list(document, "phenotypes")),
            subtypes=len(self._mapping_list(document, "has_subtypes"))
            + len(self._mapping_list(document, "subtypes")),
            experimental_models=len(self._mapping_list(document, "experimental_models")),
            animal_models=len(self._mapping_list(document, "animal_models")),
            model_organism_evidence_items=polarity_counts["MODEL_ORGANISM"],
            explicit_gaps_or_controversies=sum(
                1 for kind in kinds if kind in {"KNOWLEDGE_GAP", "CONTROVERSY"}
            ),
            human_model_mismatch_discussions=kinds.count("HUMAN_MODEL_MISMATCH"),
            upstream_proposed_experiments=sum(
                len(_as_sequence(item.get("proposed_experiments"))) for item in discussions
            ),
            clinical_trials=len(_as_sequence(document.get("clinical_trials"))),
            datasets=len(_as_sequence(document.get("datasets"))),
            references=len(_as_sequence(document.get("references"))),
        )

    def _import_disease(
        self,
        document: Mapping[str, Any],
        name: str,
        source_locator: str,
        snapshot: SourceSnapshot,
    ) -> Disease:
        disease_id = _stable_id("dismech:disease", source_locator, name)
        identity_payload = {key: document[key] for key in DISEASE_IDENTITY_KEYS if key in document}
        mondo = _descriptor_id(document.get("disease_term"))
        if mondo is None or not mondo.startswith("MONDO:"):
            mondo = self._mapping_curie(document, "mondo_mappings", "MONDO:")
            if mondo is not None:
                self._warn(
                    "MONDO_FROM_MAPPINGS",
                    "mappings.mondo_mappings",
                    f"disease_term lacks a MONDO id; using mapping {mondo}.",
                )
        updated = document.get("updated_date") or document.get("creation_date")
        return Disease(
            id=disease_id,
            canonical_name=name,
            mondo_id=mondo,
            omim_id=None,
            orphanet_id=None,
            aliases=_strings(document.get("synonyms")),
            description=self._optional_text(document.get("description")),
            parents=_strings(document.get("parents")),
            disease_type=str(document.get("category")) if document.get("category") else None,
            source="DisMech",
            source_version=self.source_version,
            source_date=str(updated) if updated else None,
            provenance=self._provenance(snapshot, "$", identity_payload),
        )

    def _mapping_curie(
        self, document: Mapping[str, Any], slot: str, prefix: str
    ) -> str | None:
        mappings = document.get("mappings")
        if not isinstance(mappings, Mapping):
            return None
        for item in _as_sequence(mappings.get(slot)):
            candidate = _descriptor_id(item)
            if candidate and candidate.startswith(prefix):
                return candidate
        return None

    def _import_evidence(
        self,
        raw_items: object,
        claim_id: str,
        snapshot: SourceSnapshot,
        path: str,
    ) -> list[EvidenceItem]:
        result: list[EvidenceItem] = []
        for index, item in enumerate(_as_sequence(raw_items)):
            item_path = f"{path}[{index}]"
            if not isinstance(item, Mapping):
                raise DisMechImportError(f"{item_path}: evidence must be an object")
            reference = self._required_text(item, "reference", item_path)
            span = item.get("snippet")
            if not isinstance(span, str) or not span.strip():
                # An exact span cannot be fabricated. The pointer stays verbatim in the
                # parent's provenance payload and is surfaced here as a warning.
                self._warn(
                    "EVIDENCE_WITHOUT_SNIPPET",
                    item_path,
                    f"Evidence {reference} has no snippet; not normalized into an "
                    "EvidenceItem (retained in the parent provenance payload).",
                )
                continue
            support = str(item.get("supports", "SUPPORT")).upper()
            relation = {
                "SUPPORT": EvidenceRelation.SUPPORTS,
                "REFUTE": EvidenceRelation.REFUTES,
                "NO_EVIDENCE": EvidenceRelation.NEUTRAL,
                "PARTIAL": EvidenceRelation.QUALIFIES,
            }.get(support)
            if relation is None:
                self._warn(
                    "UNKNOWN_SUPPORTS_VALUE",
                    f"{item_path}.supports",
                    f"Unrecognized supports value {support!r}; mapped to NEUTRAL.",
                )
                relation = EvidenceRelation.NEUTRAL
            quote_role = str(item.get("quote_role", "")).upper()
            origin = {
                "PRIMARY_RESULT": EvidenceOrigin.PRIMARY_RESULT,
                "BACKGROUND": EvidenceOrigin.CITED_BACKGROUND,
                "REVIEW_SYNTHESIS": EvidenceOrigin.REVIEW_SYNTHESIS,
            }.get(quote_role, EvidenceOrigin.DATABASE_ASSERTION)
            modality = {
                "HUMAN_CLINICAL": EvidenceModality.HUMAN_CLINICAL,
                "MODEL_ORGANISM": EvidenceModality.MODEL_ORGANISM,
                "IN_VITRO": EvidenceModality.IN_VITRO,
                "COMPUTATIONAL": EvidenceModality.COMPUTATIONAL,
            }.get(str(item.get("evidence_source", "OTHER")).upper(), EvidenceModality.OTHER)
            section = {
                "BACKGROUND": SourceSection.INTRODUCTION,
                "REVIEW_SYNTHESIS": SourceSection.REVIEW_SUMMARY,
            }.get(quote_role, SourceSection.UNKNOWN)
            try:
                identifiers = split_reference(reference)
                provenance = self._provenance(snapshot, item_path, dict(item))
                result.append(
                    EvidenceItem(
                        evidence_id=_stable_id(
                            "dismech:evidence", claim_id, item_path, reference, span
                        ),
                        claim_id=claim_id,
                        **identifiers,
                        title=self._optional_text(item.get("reference_title")),
                        exact_supported_span=span,
                        source_section=section,
                        evidence_relation=relation,
                        evidence_origin=origin,
                        evidence_modality=modality,
                        study_design=StudyDesign.UNKNOWN,
                        species=(
                            ("Homo sapiens",)
                            if modality is EvidenceModality.HUMAN_CLINICAL
                            else ()
                        ),
                        limitations=(
                            "Imported DisMech evidence pointer; study design and context "
                            "require independent review.",
                        ),
                        curator_explanation=self._optional_text(item.get("explanation")),
                        upstream_directness=self._optional_text(item.get("directness")),
                        retrieval_date=self.retrieval_date,
                        provenance=provenance,
                    )
                )
            except ValueError as exc:
                self._warn(
                    "INVALID_REFERENCE_SYNTAX",
                    f"{item_path}.reference",
                    f"Reference {reference!r} failed identifier validation ({exc}); "
                    "not normalized (retained in the parent provenance payload).",
                )
        return result

    def _import_genes(self, document: Mapping[str, Any], disease_id: str) -> tuple[Gene, ...]:
        result: list[Gene] = []
        for index, item in enumerate(self._mapping_list(document, "genetic")):
            descriptor = item.get("gene_term")
            symbol = None
            hgnc = None
            if isinstance(descriptor, Mapping):
                symbol = descriptor.get("preferred_term") or _descriptor_label(descriptor)
                hgnc = _descriptor_id(descriptor)
            if not symbol and item.get("name"):
                symbol = item["name"]
            if not symbol:
                self._warn(
                    "GENETIC_ENTRY_WITHOUT_GENE",
                    f"genetic[{index}]",
                    "Genetic entry has no gene_term or name; preserved as a record only.",
                )
                continue
            result.append(
                Gene(
                    id=_stable_id("dismech:gene", disease_id, str(index), str(symbol)),
                    hgnc_id=hgnc if hgnc and hgnc.startswith("HGNC:") else None,
                    symbol=str(symbol),
                )
            )
        return tuple(result)

    def _import_variants(self, document: Mapping[str, Any], disease_id: str) -> tuple[Variant, ...]:
        located: list[tuple[str, Mapping[str, Any], str | None]] = [
            (f"variants[{index}]", item, None)
            for index, item in enumerate(self._mapping_list(document, "variants"))
        ]
        for gene_index, gene in enumerate(self._mapping_list(document, "genetic")):
            gene_symbol = None
            if isinstance(gene.get("gene_term"), Mapping):
                gene_symbol = gene["gene_term"].get("preferred_term")
            gene_symbol = gene_symbol or gene.get("name")
            for index, item in enumerate(
                self._mapping_list(gene, "variants", parent=f"genetic[{gene_index}]")
            ):
                located.append(
                    (f"genetic[{gene_index}].variants[{index}]", item, gene_symbol)
                )
        result: list[Variant] = []
        for path, item, parent_gene in located:
            label = self._optional_text(item.get("name"))
            gene_value = item.get("gene")
            gene_label = (
                gene_value.get("preferred_term") or _descriptor_label(gene_value)
                if isinstance(gene_value, Mapping)
                else self._optional_text(gene_value)
            ) or parent_gene
            result.append(
                Variant(
                    id=_stable_id("dismech:variant", disease_id, path, label or ""),
                    upstream_label=label,
                    variant_class=self._optional_text(
                        item.get("variant_type") or item.get("type")
                    ),
                    clinical_significance=self._optional_text(item.get("clinical_significance")),
                    associated_gene=str(gene_label) if gene_label else None,
                    source_object_path=path,
                )
            )
        return tuple(result)

    def _import_hypotheses(
        self, document: Mapping[str, Any], disease_id: str
    ) -> tuple[MechanisticHypothesis, ...]:
        result: list[MechanisticHypothesis] = []
        for index, item in enumerate(self._mapping_list(document, "mechanistic_hypotheses")):
            identifier = str(item.get("hypothesis_group_id") or f"hypothesis-{index}")
            statement = str(item.get("description") or item.get("hypothesis_label") or identifier)
            status_raw = str(item.get("status") or "").upper()
            status = (
                HypothesisStatus.CONTRADICTED
                if status_raw == "DEPRECATED"
                else HypothesisStatus.UNRESOLVED
            )
            result.append(
                MechanisticHypothesis(
                    hypothesis_id=_stable_id("dismech:hypothesis", disease_id, identifier),
                    statement=statement,
                    upstream_trigger="Not atomically specified in upstream hypothesis metadata",
                    proposed_mechanism=statement,
                    downstream_consequence="Requires atomic claim decomposition",
                    disease_context=disease_id,
                    subtype_context=_strings(item.get("applies_to_subtypes")),
                    status=status,
                    upstream_status=status_raw or None,
                    unresolved_assumptions=("Imported hypothesis requires evidence refinement.",),
                    created_by="DisMech",
                )
            )
        return tuple(result)

    def _import_discussion_gaps(
        self, document: Mapping[str, Any], disease_id: str
    ) -> tuple[KnowledgeGap, ...]:
        result: list[KnowledgeGap] = []
        for index, item in enumerate(self._mapping_list(document, "discussions")):
            if str(item.get("kind", "")).upper() != "KNOWLEDGE_GAP":
                continue
            upstream_id = str(item.get("discussion_id") or f"discussion-{index}")
            gap_id = _stable_id("dismech:gap", disease_id, upstream_id)
            result.append(
                KnowledgeGap(
                    gap_id=gap_id,
                    question=str(item.get("prompt") or upstream_id),
                    gap_type=GapType.OTHER,
                    related_claims=(),
                    related_edges=_strings(item.get("attaches_to")),
                    scope="Imported DisMech KNOWLEDGE_GAP discussion",
                    why_it_matters=str(item.get("rationale") or "Requires review"),
                    current_evidence_summary=(
                        "Upstream discussion imported; evidence not yet adjudicated."
                    ),
                    contradictory_evidence_summary="Not yet assessed.",
                    search_coverage=pending_search_coverage(f"coverage-{gap_id}"),
                    missing_evidence_type=("To be resolved during refinement",),
                    required_context=(),
                    priority_reason=GapPriorityDimensions(
                        causal_centrality="not assessed",
                        downstream_dependence="not assessed",
                        evidence_conflict="not assessed",
                        translational_relevance="not assessed",
                        experimental_tractability="not assessed",
                        available_assets="not assessed",
                        discriminates_competing_hypotheses="not assessed",
                    ),
                    resolvability="Requires refinement review",
                    proposed_discriminating_test=None,
                    status=str(item.get("status") or "OPEN"),
                )
            )
        return tuple(result)

    def _preserve_records(
        self, document: Mapping[str, Any], disease_id: str, snapshot: SourceSnapshot
    ) -> tuple[PreservedUpstreamRecord, ...]:
        """Keep every top-level item outside pathophysiology/phenotypes verbatim."""
        reasons = {
            "genetic": "Gene identity normalized; association, inheritance, case fractions, "
            "validity, variant clinical/functional detail and evidence are not typed.",
            "variants": "Variant label/class/significance normalized; functional effects, "
            "genomic context and evidence are not typed.",
            "mechanistic_hypotheses": "Hypothesis statement/status normalized; hypothesis "
            "evidence and notes are not typed.",
            "discussions": "Only KNOWLEDGE_GAP prompts become KnowledgeGap; discussion "
            "evidence, proposed experiments and other kinds are not typed.",
        }
        records: list[PreservedUpstreamRecord] = []
        handled = {"pathophysiology", "phenotypes", *DISEASE_IDENTITY_KEYS}
        for key, value in document.items():
            if key in handled:
                continue
            if key not in PRESERVED_SECTIONS and key not in PARTIALLY_NORMALIZED_SECTIONS:
                self._warn(
                    "UNDECLARED_TOP_LEVEL_SECTION",
                    key,
                    f"Top-level key {key!r} has no declared disposition; preserved verbatim.",
                )
            reason = reasons.get(key, f"Section {key!r} is not normalized in V1.")
            items: list[tuple[str, object]] = (
                [(f"{key}[{index}]", item) for index, item in enumerate(value)]
                if isinstance(value, list)
                else [(key, value)]
            )
            for path, item in items:
                payload = dict(item) if isinstance(item, Mapping) else {"value": item}
                records.append(
                    PreservedUpstreamRecord(
                        record_id=_stable_id("dismech:record", disease_id, path),
                        section=key,
                        reason=reason,
                        payload_sha256=_payload_hash(payload),
                        provenance=self._provenance(snapshot, path, payload),
                    )
                )
        return tuple(records)

    def _referenced_target(
        self, disease_id: str, label: str, snapshot: SourceSnapshot, path: str
    ) -> MechanismNode:
        provenance = self._provenance(snapshot, path, {"target": label})
        return MechanismNode(
            id=_stable_id("dismech:referenced-node", disease_id, label),
            label=label,
            category=MechanismNodeCategory.UNSPECIFIED,
            description="Referenced by an upstream edge; no matching imported node record.",
            source_kind=ProvenanceKind.CURATED,
            provenance=provenance,
        )

    def _node_category(self, item: Mapping[str, Any]) -> MechanismNodeCategory:
        scale = str(item.get("biological_scale", "")).lower()
        if "molecular" in scale:
            return MechanismNodeCategory.MOLECULAR_EVENT
        if "cell" in scale:
            return MechanismNodeCategory.CELLULAR_PROCESS
        if "tissue" in scale:
            return MechanismNodeCategory.TISSUE_PROCESS
        if "organism" in scale:
            return MechanismNodeCategory.PHYSIOLOGICAL_PROCESS
        if item.get("pathways"):
            return MechanismNodeCategory.PATHWAY
        if item.get("protein_complexes"):
            return MechanismNodeCategory.PROTEIN_COMPLEX
        return MechanismNodeCategory.UNSPECIFIED

    def _node_annotations(self, item: Mapping[str, Any]) -> tuple[OntologyAnnotation, ...]:
        result: list[OntologyAnnotation] = []
        for slot in NODE_DESCRIPTOR_SLOTS:
            for descriptor in _as_sequence(item.get(slot)):
                if isinstance(descriptor, Mapping):
                    result.append(
                        OntologyAnnotation(
                            slot=slot,
                            preferred_term=self._optional_text(descriptor.get("preferred_term")),
                            term_id=_descriptor_id(descriptor),
                            term_label=_descriptor_label(descriptor),
                            modifier=self._optional_text(descriptor.get("modifier")),
                        )
                    )
                elif isinstance(descriptor, str):
                    result.append(OntologyAnnotation(slot=slot, preferred_term=descriptor))
        return tuple(result)

    @staticmethod
    def _annotation_labels(
        annotations: Sequence[OntologyAnnotation], slot: str
    ) -> tuple[str, ...]:
        return tuple(
            item.preferred_term or item.term_label or item.term_id or ""
            for item in annotations
            if item.slot == slot
        )

    def _node_context(self, item: Mapping[str, Any]) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                (
                    *_strings(item.get("cell_types")),
                    *_strings(item.get("locations")),
                    *_strings(item.get("subtypes")),
                    *_strings(item.get("assays")),
                )
            )
        )

    def _warn(self, code: str, path: str, message: str) -> None:
        self._warnings.append(ImportWarning(code=code, path=path, message=message))

    def _provenance(
        self, snapshot: SourceSnapshot, path: str, payload: dict[str, Any]
    ) -> Provenance:
        return Provenance(
            kind=ProvenanceKind.CURATED,
            source_name="DisMech",
            source_version=self.source_version,
            source_object_path=path,
            source_snapshot_sha256=snapshot.sha256,
            extraction_method="deterministic_dismech_adapter_v2",
            source_payload=payload,
        )

    @staticmethod
    def _mapping_list(
        document: Mapping[str, Any], key: str, parent: str = "$"
    ) -> list[Mapping[str, Any]]:
        value = document.get(key)
        if value is None:
            return []
        if not isinstance(value, list):
            raise DisMechImportError(f"{parent}.{key}: expected a list")
        result: list[Mapping[str, Any]] = []
        for index, item in enumerate(value):
            if not isinstance(item, Mapping):
                raise DisMechImportError(f"{parent}.{key}[{index}]: expected an object")
            result.append(item)
        return result

    @staticmethod
    def _required_text(document: Mapping[str, Any], key: str, path: str) -> str:
        value = document.get(key)
        if not isinstance(value, str) or not value.strip():
            raise DisMechImportError(f"{path}.{key}: required non-empty text")
        return value.strip()

    @staticmethod
    def _optional_text(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, int | float | bool):
            return str(value)
        return json.dumps(value, sort_keys=True, default=str)
