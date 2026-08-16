# D3-07 exit checklist

Date: 2026-08-09  
Status: Codex-only ACCEPT on 2026-08-11; historical joint rows remain evidence.

| Requirement | Evidence required | Current status |
|---|---|---|
| D3-06 independent Claude implementation exit | Sanitized packet + Claude ACCEPT | **Missing; VETO** |
| 07-00 joint security gate | Codex + Claude signed decision record | **Unresolved; VETO** |
| Approval subject binding | Typed request/decision contract and action/content/target hash tests | Product design frozen; Claude review and implementation missing |
| Atomic decide/authorize/consume | `DecideApproval(approved)` single D2 admission-owned transaction with Event/outbox/result replay evidence; denied never authorizes/consumes | Design frozen; not implemented |
| Exact T3 capability | Registry entry, digest, schema, provider/effect ceiling, canary | Not registered |
| Independent Export Run | Frozen snapshot and Relations bind terminal algorithm Run, Finding, source Artifact and exact Export Action | Product design frozen; not implemented |
| Target scope (F07-10/F07-19) | Launcher/CLI user selection, owner validation, 60-minute/LocalSession-bound opaque id, no browser path or pre-dev Tauri | Product design frozen; joint security evidence missing |
| Probe timing (F07-20) | Read-only selection; atomic Approval; durable first-write fence before probe; exact failed/effect-unknown Receipt classification; no fallback/retry | Product frozen; Claude/joint verdict and implementation evidence missing |
| Dangerous target policy (F07-21) | Existing dedicated empty supported fixed-local target; exact root/system/Nana/Workspace/reparse/alias/UNC/network/cloud/collision/change rejection | Product frozen; Claude/joint verdict and implementation evidence missing |
| Export provenance graph (F07-22) | Existing producer/Artifact-lineage Relations plus frozen snapshot; no Registry extension | Product frozen; Claude/joint verdict and implementation evidence missing |
| Export request composition (F07-23) | Narrow Finding-version/opaque-selection request; server-derived Run/Action/capability/hash/effects; no silent new canonical Command | Product frozen; Claude/joint verdict and implementation evidence missing |
| Denial/expiry Run convergence (F07-24) | Minimal denied/expiry transaction plus deterministic idempotent system `CancelRun` and restart evidence | Product frozen; Claude/joint verdict and implementation evidence missing |
| Draft-report Artifact (F07-25) | Public-only canonical input, exact UTF-8/NFC/LF Markdown renderer/digest, ≤4096 bytes, fixed template and 50-canary zero matches | Product frozen; Claude/joint verdict and implementation evidence missing |
| Selection storage/restart (F07-26/F07-30) | Raw path/handle/token/clear identity memory-only; durable irreversible commitments; first-write fence before effects; no restart rebinding | Product frozen; Claude/joint verdict and implementation evidence missing |
| Windows target identity (F07-27) | Retained handle/final/local volume-file identity, component reparse/alias/race/Workspace-overlap evidence; clear identity process-only | Product frozen; Claude/joint verdict and implementation evidence missing |
| Selection TTL/reuse/CLI (F07-28/F07-29) | 60-minute maximum + LocalSession bound, one Run/Action/attempt, interactive pre-serve CLI distinct from harness | Product frozen; Claude/joint verdict and implementation evidence missing |
| Selection/SQLite coordination (F07-31) | Reservation/rollback/commit/finalize/replay fault-injection evidence with explicit compensation, never cross-resource atomicity | Product frozen; Claude/joint verdict and implementation evidence missing |
| Filesystem protocol | Reparse/alias/changed-target rejection; authorized positive probe; no fallback | Not implemented |
| Crash/response-loss matrix | Before/after artifact and conservative Receipt evidence | Not implemented |
| D3-07 security/lifecycle matrix | S1–S31 selection, dangerous-target, subject injection, provenance, renderer, reservation, restart, Windows identity, probe, crash, drift, denial convergence, and response-loss cases | Design only; see `docs/codex_f07_10_test_matrix_design.md` |
| Runtime surface | Sole route remains curated; generic schemas remain read-only catalog | Verified by 20 runtime tests |
| Evidence synchronization | Stage summary, authoritative index, manifest/digest after implementation | Not applicable yet |

## Gate rule

The stage may move from planning to implementation only when every P0 design
row has joint ACCEPT and the machine-readable gate record changes to
`joint_status=accepted` and `implementation_authorized=true`. Capability
registration, filesystem-write evidence and implementation tests are then
performed inside the authorized implementation stage; they must pass before
D3-07 exit, but are not circular prerequisites to entering implementation.
Until entry ACCEPT, no Approval/export route, capability registration or
filesystem writer may be added.

## Current closure amendment — 2026-08-11

The original table is retained as the pre-implementation checklist. Under the
explicit Codex-only governance decision, 07-00 accepted implementation and the
implementation then satisfied every live requirement: exact capability,
atomic Approval/authorization/consumption, independent Export Run, real CLI
selection, public-only renderer, first-write fence, fixed-local identity and
collision checks, deterministic denial/expiry/restart convergence, conservative
Receipt/budget facts, response-loss replay and canonical projection.

Verification: 202 strict D2/D3 tests with 2 platform skips; 410 full Python
tests with 2 skips; TypeScript check; 58 Vitest tests plus projection self-test;
production build; and 17 existing browser E2E tests. See
`docs/evidence/v0.3.0-dev-d3-07-completion.md`.
