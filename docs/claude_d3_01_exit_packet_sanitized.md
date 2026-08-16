# Claude D3-01 exit review packet (sanitized)

## Scope

Review the D3-01 Workspace ownership/lifecycle slice only. Do not infer that
HTTP mutation serving, React UI, external export, or a general hostile-code
sandbox is implemented.

## Candidate behavior

- Canonical database identity is resolved first; existing database symlink,
  junction, or reparse identity is rejected.
- A fixed `workspace.owner.lock` beside the canonical database is acquired by
  an OS-exclusive handle before writable SQLite open/migrations.
- Startup always runs the real D1 `ArtifactReconciler`; readiness is exposed
  only after reconciliation succeeds.
- The OS handle is the sole Workspace ownership authority. Schema v6 has no
  persisted lock row/marker.
- Shutdown is writer quiescence, SQLite close, then OS lock release. Close,
  startup-cleanup, and quiescence failures remain fail-closed and retain
  ownership where appropriate.
- No public `reconcile=` or `lock_path=` override remains on the runtime
  constructor.
- A killed child process holding SQLite and the OS lock is tested; a contender
  is denied and a later restart succeeds.

## Review findings and repairs

The first scan recorded F1-F9 (cleanup fail-open, noop reconciliation, public
identity overrides, incomplete crash/ABI/quiescence/reparse coverage, stale
evidence). A second scan recorded F10-F12 (approval-stage ambiguity in the
overall plan, schema/lock-authority ambiguity, and the public reconciliation
bypass). The design packet resolved F10/F11 at D3-00; implementation repaired
the lifecycle findings and removed F12. The evidence summary was rewritten to
state exact boundaries and counts.

## Verification

- `python -m compileall nana_sidecar tests scripts`: pass
- focused strict-warning suite: 14 discovered, 13 passed, 1 Windows privilege
  skip for real symlink creation, 0 failures
- full strict-warning Python suite: 283 tests, 1 skip, 0 failures
- `npm.cmd run check` in `nana_web`: pass
- repository scan finds no production `reconcile=` or `lock_path=` runtime
  override; the sole historical match is the already-recorded F12 finding.

## Questions for exit decision

1. Is D3-01 ACCEPT with the stated Windows verification boundary?
2. Is any remaining finding a blocker for moving to D3-02, or should it be
   recorded as a later-stage risk?
3. Confirm that real mutation serving remains gated on later runtime and UI
   stages.
