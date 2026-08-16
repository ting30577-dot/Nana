# Nana D3-00 neutral evidence packet (sanitized)

This packet contains only the evidence and decision questions required for an
independent D3 proposal. It contains no credentials, environment values,
machine identity, hardware identity, private network data, or user-specific
absolute paths. All file references are repository-relative.

## Collaboration rule

Codex and Claude are equal, read-only co-designers for important decisions.
Each must first propose independently from this neutral packet. Proposals are
then exchanged for review, rebuttal, and explicit convergence. An unresolved
material objection must be recorded as `NOT CONSENSUS`, not softened into an
acceptance. Claude must not modify the repository.

## Current verified baseline

- D0: complete.
- D1: complete.
- D2: jointly accepted, strictly limited to the trusted frozen
  `python.unittest.locked` execution surface.
- Fresh local baseline on 2026-08-01:
  - `python -m compileall nana_sidecar tests scripts`: pass.
  - `python -m unittest`: 269 tests, OK.
  - `npm.cmd run check` in `nana_web`: pass.
  - The full Python suite still emits the known legacy PySide6 shutdown
    `ResourceWarning`; the seven D2 modules previously pass with that warning
    promoted to an error.
- D2 evidence manifest: 102 entries, no recorded hash errors; digest
  `1cbb07d25a1333e0a860182f0a47f915601c90af083b6e8b9daf4ec5aedd7f5d`.

## D2 facts available to D3

D3 may consume only the established facts in `runs`, `actions`,
`action_authorizations`, `events`, `outbox_events`, `action_receipts`,
`artifacts`, the command idempotency records, artifact lifecycle projections,
structured errors, and the D2 replay fixture.

D3 must not:

- query `PolicyGrant` or `Approval` to re-derive authorization;
- bypass D2 admission, scheduler, or executor;
- treat UI local state as canonical truth;
- render `effect_unknown` as success;
- render `paused/cancel_requested` as fully cancelled or resumable pause;
- collapse `artifact.reconciled(available)` into an ordinary commit;
- generalize the frozen worker evidence into a hostile-code sandbox claim;
- expose arbitrary shell or arbitrary Python execution.

The browser SSE client must use authenticated `fetch + ReadableStream`, not
native `EventSource`. Stable Event ID, at-least-once delivery, cursor reconnect,
ordered replay, and client de-duplication remain mandatory.

## Hard gate before any real mutation serving

The runtime must implement and test a Workspace ownership lifecycle:

1. obtain a non-blocking process-exclusive OS lock for the resolved Workspace
   identity before opening canonical SQLite in writable mode;
2. keep the lock across migration, reconciliation, all writers, and shutdown;
3. report ready only after reconciliation converges;
4. fail closed for a second instance;
5. stop accepting mutations and quiesce writers, then close SQLite/WAL, and
   only then release the lock;
6. test sidecar crash OS-release and restart recovery, second-instance denial,
   and the exact ready/close ordering.

Before this gate passes, only read-only UI, fixture/replay, projection, and
design work may run.

## HTTP and OpenAPI facts

- The checked-in D0 OpenAPI app and the D1 authenticated runtime/SSE app are
  intentionally separate.
- Merging them is an explicit D3 decision and requires a regenerated OpenAPI
  snapshot/client plus regression evidence.
- Runtime HTTP authentication is default-deny. Only exact existing bootstrap
  paths are public. Any new public/bootstrap route requires separate security
  review.
- If browser CORS is added, only the exact per-launch loopback Origin, required
  methods, and required headers may pass. `OPTIONS` must not become a blanket
  anonymous bypass.
- There is no real HTTP mutation route today.

## Current web and application-service shape

- `nana_web` currently contains generated TypeScript contracts and a strict
  type check only. React and browser E2E infrastructure are not installed.
- The runtime has authenticated SSE and default-deny route middleware.
- The only implemented command transaction is a narrow `RevisePlan` service;
  the full typed command catalog does not imply full runtime handlers.
- D2 has admission, scheduling, the locked executor, budgets, Receipts, and
  durable authorization material, but no public runtime mutation composition.

## D3 product target and scope ceiling

D3 is the first bridge from safe runtime to a usable product surface. Its core
target is not a decorative UI: it must project D2 facts into the minimum React
end-to-end development journey so a user can understand and complete:

`create -> resource/locator -> editable plan -> locked test run -> activity ->
artifact -> finding draft -> one-time approval -> external draft export receipt`

The frozen algorithm question remains variable-length sliding-window
monotonicity with negative numbers. D3 must not pull alpha.1 work into dev:
counterexample research, three implementations, property tests, benchmarks,
finding review, and final Decision remain deferred.

The UI must clearly explain canonical states including authorization pending,
running, termination in progress, cancelled, failed, orphaned,
`effect_unknown`, reconciled Artifact, and Receipt. Refresh/reconnect must
rebuild from canonical facts. Keyboard use and Windows 125%/150% DPI are part
of the D3 gate. The dev journey must pass ten consecutive browser E2E runs.

## Evidence reviewed

- `docs/d2_runtime_handoff.md`
- `docs/d2_07_exit_review.md`
- `docs/d2_07_decision_record.md`
- `fixtures/v0.3.0-dev/d2_runtime_handoff_replay.json`
- `fixtures/v0.3.0-dev/d2_security_matrices.json`
- `docs/evidence/v0.3.0-dev-d2-manifest.txt`
- authoritative specifications 00, 05, 06, 07, 10, 11, and 12

## Independent proposal requested from Claude

Please independently propose a D3 decomposition and decision record. Include:

1. the smallest complete D3 architecture that can reach the dev journey without
   bypassing D2 facts;
2. exact ordering and API boundaries for Workspace lock, database ownership,
   reconciliation, readiness, mutation serving, and shutdown;
3. an explicit ACCEPT or VETO recommendation for OpenAPI/runtime app merging,
   including CORS/bootstrap implications;
4. which read models and minimal mutation application services/routes are
   required, and which are explicitly excluded;
5. the React projection/store and authenticated SSE reconnect algorithm;
6. an E2E/test matrix, including ten consecutive journeys and negative-state
   coverage;
7. phase-by-phase stop conditions and evidence outputs;
8. likely shortcuts that should be vetoed;
9. risks or counterarguments that could invalidate your own proposal.

Do not assume Codex's design. Return reviewable conclusions, evidence,
trade-offs, risks, and explicit decision labels rather than hidden reasoning.
