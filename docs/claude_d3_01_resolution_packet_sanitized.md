# D3-01 F13-F15 resolution packet (sanitized)

## Codex cross-check

### F13

The focused suite contains an executed deterministic positive rejection test:

1. create a real database file;
2. patch the filesystem identity probe `Path.is_symlink` to return true;
3. construct `WorkspaceRuntime`;
4. assert `WorkspaceLockError` with the canonical-database reparse message.

This test passed in the strict-warning run. The separate real Windows symlink
test is still privilege-skipped and remains a declared environment boundary.
This matches Claude's proposed acceptable closure using a mocked identity
probe; no claim of real symlink creation is made.

### F14

| Failure branch | SQLite state | Ownership decision |
|---|---|---|
| startup fails before SQLite exists, or SQLite closes successfully during cleanup | closed/absent | release OS lock |
| startup cleanup cannot close SQLite | possibly open | retain OS lock; `startup_close_failed` |
| writer quiescence fails | open | retain OS lock and connection; `drain_failed` |
| normal shutdown cannot close SQLite | possibly open | retain OS lock; `close_failed` |
| SQLite closes, then OS release reports failure | closed | report `lock_release_failed`; do not claim closed |
| reconciliation fails and SQLite cleanup succeeds | closed | release OS lock; later restart may reconcile and become ready |

### F15

The child prints `READY` only after acquiring the OS lock, opening SQLite, and
completing reconciliation. The contender is attempted while the child is alive
and must fail. Only then does the test call `kill()` followed by
`wait(timeout=5)`. Recovery is attempted after `wait` confirms process
termination, so it does not race an unconfirmed live process or use a fixed
sleep.

## Requested decision

Confirm F13-F15 CLOSED and return a final D3-01 `ACCEPT`, `VETO`, or
`尚未达成共识`. Real mutation serving remains disabled.
