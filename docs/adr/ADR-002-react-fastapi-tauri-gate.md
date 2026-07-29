# ADR-002: React/TypeScript + FastAPI; Tauri is a later gate

- Status: accepted
- Date: 2026-07-29
- Milestone: v0.3.0-dev

## Decision

- React/TypeScript owns UI and disposable projections.
- Python 3.12 + FastAPI owns domain services and canonical writes.
- The UI never writes SQLite directly.
- Web completes the dev vertical journey before a Tauri 2 spike begins.
- A secure local-Web fallback is allowed only after its separate security gate.

## D0 implementation

`nana_sidecar` exposes a read-only health/version/schema handshake and OpenAPI.
`nana_web` consumes generated TypeScript types. No mutation route exists until
the command/idempotency runtime is implemented.

## Reversal

Changing language/process ownership or bringing Tauri into dev requires user
approval.
