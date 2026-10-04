"""Capability, collaborator, and reusable-asset candidates."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ReuseStatus(StrEnum):
    VALIDATED_FOR = "validated_for"
    POSSIBLY_REUSABLE = "possibly_reusable"
    REQUIRES_VALIDATION = "requires_validation"
    UNKNOWN = "unknown"


class Capability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_id: str
    name: str
    evidence_ids: tuple[str, ...] = ()


class ResearchAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str
    asset_type: str
    name: str
    owner: str | None = None
    organization: str | None = None
    disease: tuple[str, ...] = ()
    mechanism: tuple[str, ...] = ()
    availability: str | None = None
    repository: str | None = None
    source: str
    evidence_ids: tuple[str, ...]
    last_verified: date
    reuse_status: ReuseStatus = ReuseStatus.UNKNOWN
    adaptation_requirements: tuple[str, ...] = ()


class Person(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    person_id: str
    name: str
    institution: str | None = None
    orcid: str | None = None
    publication_ids: tuple[str, ...] = ()
    grant_ids: tuple[str, ...] = ()
    expertise: tuple[str, ...] = ()
    mechanisms: tuple[str, ...] = ()
    diseases: tuple[str, ...] = ()
    asset_ids: tuple[str, ...] = ()
    contact_source: str | None = None
    verified_date: date
    provenance_sources: tuple[str, ...]


class Organization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: str
    name: str
    organization_type: str
    source: str
    verified_date: date

