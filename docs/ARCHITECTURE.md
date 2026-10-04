# Architecture

## Boundary rule

Postgres is the audit source of truth. Neo4j is a rebuildable traversal index.
External APIs and model providers are adapters. Domain objects import none of
them.

```text
read-only sources -> adapters -> source snapshots -> domain objects (Postgres)
                                            |               |
                                            |               v
                                            +------> Neo4j projection
                                                            |
claim extraction -> retrieval -> independent review -> synthesis -> gap
                                                            |
                                                            v
                                                hypothesis -> experiment
                                                            |
                                                            v
                                                capability -> asset/person
```

## Scientific stage separation

1. Import stores upstream bytes/hash/version and maps without rewriting.
2. Extraction decomposes prose; it does not decide truth.
3. Retrieval produces candidates and complete query/source coverage records.
4. Review evaluates one claim/passage pair, blind to extractor reasoning.
5. Context resolution makes species/tissue/cell/variant/model scope explicit.
6. Synthesis assigns a categorical status with evidence-ID rationale.
7. Gap detection operates on consequential weak links, not paper counts.
8. Experiment planning is allowed only for a resolved question and must include
   a result that weakens the hypothesis.
9. Capability matching produces sourced candidates, never implied availability.

## Packages

- `domain`: provider-independent immutable scientific records and validators.
- `adapters/dismech`: tolerant boundary DTOs and a strict normalized import.
- `adapters/monarch`: typed v3 request/response boundary (next implementation).
- `services`: use cases; no HTTP or persistence logic.
- `graph`: deterministic graph projection/query algorithms.
- `api`: thin transport handlers.
- `schemas`: request/response and strict model-output schemas.

## Identity and provenance

Imported IDs are deterministic UUIDv5 values derived from source namespace,
document identity, object path, and source text. Reimporting identical input is
idempotent. Every source snapshot carries SHA-256, retrieval time, source
version, and media type. Model runs must record provider/model/template/schema,
input evidence IDs, output object IDs, and timestamp.

## Failure semantics

Retrieval errors are data (`FAILED` coverage status), not empty results.
Unverifiable evidence is `UNVERIFIED`. Missing evidence means “not identified
in searched sources,” never “does not exist.” Unknown targets and malformed
identifiers fail import with a path-specific error. Scientifically meaningful
disagreement is preserved.

## Persistence plan

The current slice implements domain/import logic independent of persistence.
The next migration introduces normalized Postgres tables with JSONB source
snapshots and append-only refinement runs. A transactional projector upserts
Neo4j nodes/relationships keyed by Postgres IDs and records projection version.

## Security boundary

V1 contains public research data only. Secrets are server-side environment
variables. Future patient molecular profiles require a separate privacy and
authorization architecture; this codebase makes no HIPAA-compliance claim.

