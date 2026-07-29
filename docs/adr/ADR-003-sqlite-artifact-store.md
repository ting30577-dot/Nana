# ADR-003: SQLite canonical metadata and content-addressed Artifact Store

- Status: accepted
- Date: 2026-07-29
- Milestone: v0.3.0-dev

## Decision

SQLite in WAL mode is the canonical metadata and event store. Artifact blobs
are addressed by SHA-256 and become readable only in `available` state.
Projection and cache data must be rebuildable.

## D0 implementation

Schema v1 defines Artifact metadata and never creates legacy tables. A staged
row must carry a non-empty logical `temp_ref`; an available row cannot retain
one. The D0→D1 handoff simulation proves metadata/Event/outbox atomic rollback,
reopen, and 10,000-event cursor ordering. D1 will implement the actual staged
file write, same-volume rename, reconciliation service, HTTP SSE, and fault
injection before business data migration.

## Gate

Every documented crash window must converge without exposing an unavailable
blob. Failure blocks business migration.
