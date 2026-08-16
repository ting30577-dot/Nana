# D3-07 implementation-readiness matrix (Codex planning only)

Date: 2026-08-10  
Status: `PLANNING_ONLY`; this matrix does not authorize implementation,
capability registration, mutation routes, or filesystem writes. Claude must
independently review it together with the 07-00 packet after the relay is
available.

## Entry rule

Every row requires the D3-06 Claude implementation exit and the D3-07 07-00
joint gate to be `ACCEPT` before its implementation column may be touched. The
future module names below are proposed surfaces, not claims that code exists.

| Item | Frozen invariant | Planned implementation surface | Required verification | Evidence to register | Authorization prerequisite |
|---|---|---|---|---|---|
| 07-00 | Both independent reviews and explicit joint decision | gate JSON + decision record | packet hashes, signer decisions, all flags | gate decision JSON/Markdown | Claude + Codex `ACCEPT` |
| F07-16 | `DecideApproval(approved)` decides, authorizes and internally consumes atomically; denial never authorizes | typed approval transaction service | action-hash binding, denial, expiry, replay, response loss | Approval transaction evidence | 07-00 `ACCEPT` |
| F07-17 | Each export attempt owns an independent Export Run/Action linked to terminal algorithm Run/Finding/Artifact | export subject builder | relation graph and snapshot immutability | subject graph evidence | 07-00 `ACCEPT` |
| F07-18 | Existing aggregate/Event versions are the concurrency token; no invented revision column | owner-lane CAS adapter | competing decisions and changed subject | CAS/response-loss evidence | 07-00 `ACCEPT` |
| F07-19 | Launcher/CLI selection becomes a 60-minute LocalSession-bound opaque id; browser never supplies a path | selection registry + owner runtime | actor/session binding, expiry, one-use, no path echo | selection lifecycle evidence | 07-00 `ACCEPT` |
| F07-20 | Read-only selection → atomic Approval/consumption → durable first-write fence → probe; no fallback/retry | fence/probe coordinator | unauthorized zero-operation instrumentation; exact failure classes | fence ordering + Receipt evidence | 07-00 `ACCEPT` |
| F07-21 | Existing dedicated empty supported fixed-local target; reject roots, aliases, reparse, network/cloud, collision/change | Windows target validator | S1–S17 and identity race matrix | target safety evidence | 07-00 `ACCEPT` |
| F07-22 | Existing producer/Artifact Relations plus frozen Export snapshot; no invented graph edge | provenance projector | valid/ambiguous/missing source graph rejection | relation projection evidence | 07-00 `ACCEPT` |
| F07-23 | Narrow Finding-version + opaque-selection request; server derives all security subjects | journey request mapper | browser subject injection and schema rejection | request contract evidence | 07-00 `ACCEPT` |
| F07-24 | Denied/expired decision followed by deterministic idempotent system `CancelRun` | reconciliation coordinator | crash between minimal transaction and cancellation | restart/convergence evidence | 07-00 `ACCEPT` |
| F07-25 | Public-only canonical inputs; exact UTF-8/NFC/LF Markdown, ≤4096 bytes, fixed renderer/canary | draft-report renderer | classification, digest, canary and renderer drift matrix | Artifact/renderer evidence | 07-00 `ACCEPT` |
| F07-26 | Raw path/handle/token/clear identity memory-only; durable data only irreversible commitments | selection memory store + commitment codec | durable-row and restart secret scans | privacy/commitment evidence | 07-00 `ACCEPT` |
| F07-27 | Handle/final/local identity checks detect alias/reparse/Workspace overlap; clear identity never leaves process | Windows identity adapter | case/short-name/SUBST/mount/reparse/change cases | Windows identity evidence | 07-00 `ACCEPT` |
| F07-28 | ≤60 minutes, LocalSession bounded, one selection per attempt, expiry never exceeds selection | lifecycle clock/lease logic | expiry, drain, reuse and second-attempt rejection | TTL/reuse evidence | 07-00 `ACCEPT` |
| F07-29 | Interactive pre-serve launcher/CLI source; no path command-line argument; harness distinct | launcher selection handoff | real CLI vs `test_harness` provenance | CLI provenance evidence | 07-00 `ACCEPT` |
| F07-30 | Restart before fence fails empty; after fence is `effect_unknown`; no rebind/retry | startup reconciliation extension | crash windows and response loss | restart state matrix | 07-00 `ACCEPT` |
| F07-31 | reserve → SQLite commit → finalize compensation; never claim cross-resource atomicity | selection/SQLite coordinator | reserve/rollback/commit/finalize fault injection | compensation evidence | 07-00 `ACCEPT` |
| 07-04 | Every security/canary/crash case projects canonical facts and actual effects | D3-07 test harness | full F07-10 matrix, 50-canary, no remote publish | test manifest + digest | all design rows `ACCEPT` |
| 07-05 | First scan → one repair batch → second scan → evidence sync → Claude exit | stage evidence runner | zero unresolved F# findings and independent exit | exit review + authority sync | joint exit `ACCEPT` |

## Cross-cutting prohibitions

- No `PolicyGrant`/`Approval` re-query in the browser to infer authorization.
- No reuse of D2 `python.unittest.locked` as a hostile-code or T3 writer claim.
- No public `ConsumeApproval`, `PublishExport`, arbitrary shell/Python, remote
  publish, browser path, or optimistic success projection.
- No implementation flag, capability registry entry, mutation route or external
  byte is permitted while the machine-readable gate remains unresolved.

## Current decision

Codex accepts this as a planning matrix only. Claude review is still missing;
therefore the implementation decision remains `尚未达成共识` and all write
authorization flags remain false. The local non-implementation guard is
recorded in `docs/evidence/v0.3.0-dev-d3-07-pre-gate-guard-20260810.md` and
does not alter that decision.
