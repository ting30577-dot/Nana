# D3-06 final no-edit implementation scan

Date: 2026-08-09  
Status: Codex local ACCEPT; Claude implementation-exit verdict pending.

This scan was performed after the reopening repair batch. Runtime source was
frozen during the scan. The scan re-read the browser request contract, runtime
owner-lane bridge, D1 Artifact publication path, D2 admission/scheduler/budget/
locked-executor paths, startup reconciliation, read projections and all D3-06
focused tests.

## Hard-gate result

- Browser StartRun contains only target/revision/random-seed fields. The server
  injects the exact frozen `python.unittest.locked` capability and fixture.
- Args bytes are a D1 content-addressed Artifact and the bytes checked by D2
  preflight are the bytes represented by the immutable Action material.
- Admission, grant consumption, claim, reservation and usage settlement remain
  D2-owned. A non-claimed scheduler outcome cannot reach worker submission.
- Spawn is fenced by an append-only Event/outbox fact without changing the Run
  snapshot. Cancellation, timeout intent and recovery are owner-lane writes.
- The worker receives immutable arguments and a thread-safe cancel callback,
  never a SQLite handle. Process-tree termination failure, reader cleanup
  failure and Windows Job close failure fail closed.
- Result staged/committed Events, canonical availability, producer binding,
  provenance Relation, Receipt, usage settlement, Gate-A..H audit Events,
  Action terminal Event and Run terminal Event commit atomically.
- Startup covers proposed, authorized, claimed/no-fence, spawn-fenced,
  cancel-pending and historical terminal-Action/non-terminal-Run windows. No
  unknown execution is rerun.
- Receipt projection explicitly distinguishes measured, pre-spawn/no-charge and
  conservative-uncertain billing bases.

## Verification considered

- D3-06 focused suite: 17 tests, pass.
- D1 Artifact commit/failure/reconciliation plus D3-06: 51 tests, pass.
- D3 strict `ResourceWarning-as-error` suite: 107 tests, 2 declared platform
  skips, pass.
- Full Python suite: 372 tests, 2 declared platform skips, pass. The existing
  PySide6 shutdown warning remains outside the strict D3/D2 paths.
- TypeScript strict check: pass.
- Frontend Vitest: 23 tests plus projection self-test, pass.
- Frontend production build: pass.

## Verdict

Codex local implementation verdict is **ACCEPT** for the exact fixture-only
D3-06 boundary. This is not a joint exit. D3-07 implementation remains blocked
until the independent Claude implementation review returns ACCEPT and the
separate D3-07 07-00 joint security gate is also ACCEPT.
