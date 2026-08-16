# D3-01 first full-scan findings

The candidate implementation was scanned without edits. All findings were
consolidated before batch repair.

| ID | Severity | Finding | Decision |
|---|---|---|---|
| F1 | blocker | Startup cleanup suppresses SQLite close failure, can release the OS lock, then reports `closed` | VETO current cleanup |
| F2 | blocker | Default reconciliation is a no-op callback, not the real D1 ArtifactReconciler | VETO for D3-01 exit |
| F3 | blocker | Public `lock_path` override permits two owners of one Workspace to choose different locks | VETO configurable production lock identity |
| F4 | high | Crash child holds only the lock and does not prove OS release with writable SQLite/reconciliation lifecycle | evidence insufficient |
| F5 | high | Windows `CloseHandle` lacks explicit ctypes argument/result ABI | repair required |
| F6 | high | Shutdown has no writer-quiesce hook or fail-closed quiesce test | repair required before mutation serving |
| F7 | high | Existing lock symlink/reparse can resolve outside the database parent without an identity mismatch rejection | repair required |
| F8 | medium | Evidence summary claims a non-Windows fallback was tested in the current Windows environment | VETO inaccurate evidence |
| F9 | high | Tests lack real reconcile success/failure, startup-close failure, quiesce failure, and schema/no-lock-table assertions | evidence incomplete |

## Confirmed assertions

- Schema v6 already contains Artifact, Event, and outbox facts required by D1
  reconciliation.
- No canonical Workspace ownership/lock table or field exists.
- Therefore D3-01 requires no schema migration and OS handle ownership remains
  the only authority.

## Repair order

F1/F5/F6 lifecycle failure safety → F3/F7 identity safety → F2 real reconciler
integration → F4/F9 real-process and structure evidence → F8 evidence correction.

## Final re-review findings

The repaired candidate was fully re-scanned before these findings were added.

| ID | Severity | Finding | Decision |
|---|---|---|---|
| F10 | blocker | Existing database-file symlink/reparse can redirect SQLite while the lock remains beside the original path | VETO redirected canonical DB |
| F11 | high | Real D1 reconciler success is tested, but real reconciler failure/restart convergence is not | evidence incomplete |
| F12 | blocker | Public `reconcile=` constructor input allows a caller to bypass the mandatory real reconciler and still reach ready | VETO public bypass |

F8 also remains open until the stage evidence summary removes its untested
non-Windows claim and records the actual pass/skip counts.

## Claude exit review findings

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| F13 | high | The real Windows symlink test is privilege-skipped, so the exit packet did not prove an executed reparse rejection branch | Closed by the already-executed deterministic `Path.is_symlink` rejection test; the real-symlink skip remains an explicit environment boundary |
| F14 | medium | `where appropriate` did not enumerate which failures retain or release ownership | Closed by the explicit failure-state table in the resolution packet and evidence summary |
| F15 | medium | Child-process crash evidence might depend on an uncontrolled handle-release race | Closed: contender denial occurs while the child is alive; recovery starts only after `kill()` and successful `wait(timeout=5)` confirm process termination |

F13-F15 were recorded before resolution. Claude's first exit decision was
conditional ACCEPT / not-yet-consensus on F13; a follow-up closure review is
required before D3-01 can exit.

## Final joint decision

- F13: CLOSED
- F14: CLOSED
- F15: CLOSED
- Codex: ACCEPT
- Claude: ACCEPT
- D3-01: ACCEPT

Hard condition: real mutation serving remains disabled. The privilege-gated
real-symlink integration case remains a declared, non-blocking environment
risk to revisit before mutation serving.
