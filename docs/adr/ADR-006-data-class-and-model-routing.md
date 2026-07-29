# ADR-006: Data classification controls model routing

- Status: accepted
- Date: 2026-07-29
- Milestone: v0.3.0-dev

## Decision

Canonical data classes are `public`, `personal`, `confidential`, and `secret`.
Deterministic policy—not a model—decides whether content may reach a Provider.
Secret data never enters a model.

## D0 implementation

Project and Resource contracts require an explicit data class. The selected
fixture Resource is intentionally public and contains no credentials or
machine-identifying data.

## Gate

No model tool is enabled in D0. Later routing requires Provider registry and
the capability-specific EvalPack.
