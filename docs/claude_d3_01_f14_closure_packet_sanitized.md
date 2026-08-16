# D3-01 F14 execution evidence (sanitized)

## Strict run

Command class: focused Python unittest suite with `ResourceWarning` treated as
error.

Result: 15 discovered; 14 passed; 1 privilege-gated real-symlink skip; 0
failures.

## Executed branch tests

| Branch | Test identifier | Assertions that passed |
|---|---|---|
| startup reconciliation failure, cleanup close succeeds | `test_start_failure_releases_lock_for_restart` | first start raises and ends `closed`; a second runtime acquires the same canonical lock, reaches `ready`, and closes |
| startup reconciliation failure, cleanup close fails | `test_startup_cleanup_close_failure_retains_workspace_lock` | raises ownership-retained error; state `startup_close_failed`; event sequence has no lock release |
| writer quiescence fails | `test_quiesce_failure_retains_database_and_lock` | state `drain_failed`; connection remains non-null; event sequence has neither database close nor lock release |
| shutdown SQLite close fails | `test_database_close_failure_retains_workspace_lock` | state `close_failed`; event sequence has no lock release |
| SQLite closes, OS release reports failure | `test_lock_release_failure_never_claims_closed` | SQLite close occurs first; release raises; state `lock_release_failed`; connection is null; runtime never claims `closed` |
| real D1 reconciler fails, cleanup succeeds, restart converges | `test_real_reconciler_failure_never_reaches_ready_and_restart_converges` | first runtime never reaches ready; replacement runtime later reconciles and reaches ready |

The lock-release-failure test was added after Claude identified that exact
coverage gap; the focused strict suite was rerun after the addition.

## Requested final decision

Is F14 CLOSED? Return final D3-01 `ACCEPT`, `VETO`, or `尚未达成共识`.
F13 and F15 were already CLOSED. Real mutation serving remains disabled.
