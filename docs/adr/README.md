# Nana architecture decision records

These ADRs record decisions already confirmed by the vNext specification.
They do not reopen product planning.

| ADR | Decision | Status |
|---|---|---|
| [ADR-001](ADR-001-project-execution-loop.md) | Project Execution is the product loop | accepted |
| [ADR-002](ADR-002-react-fastapi-tauri-gate.md) | React/TypeScript + FastAPI; Tauri after Web gate | accepted |
| [ADR-003](ADR-003-sqlite-artifact-store.md) | SQLite canonical metadata + Artifact Store | accepted |
| [ADR-004](ADR-004-command-action-event-authorization.md) | Command/Action/Event/Grant/Approval/Receipt separation | accepted |
| [ADR-005](ADR-005-capability-registry.md) | Closed Capability Registry | accepted |
| [ADR-006](ADR-006-data-class-and-model-routing.md) | Data classification controls model routing | accepted |
| [ADR-007](ADR-007-execution-backend.md) | ExecutionBackend is explicit and capability-probed | accepted |
| [ADR-008](ADR-008-legacy-read-only-migration.md) | Legacy data migrates from a read-only source | accepted |

Any semantic change to these decisions requires a new superseding ADR and the
user's choice before implementation.
