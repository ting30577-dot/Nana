# ADR-008: Legacy data is a read-only migration source

- Status: accepted
- Date: 2026-07-29
- Milestone: v0.3.0-dev

## Decision

Legacy SQLite is inventoried and exported without vNext writes. Migration
starts with a dry-run report and verified backup. Ambiguous objects are
archived rather than assigned stronger semantics:

- Source may become Resource.
- Only a resolvable locator may support Evidence.
- Experiment may become a legacy Artifact/Run note.
- Insight may become a draft Finding, never a Decision.

## D0 implementation

The vNext schema is isolated and tests assert that no legacy tables are
created. No deletion, migration, or dual-write path is present.

## Gate

Inventory/hash equality, zero-write dry run, and object-level restore must pass
before migration.
