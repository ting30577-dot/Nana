# D3-06 batch repair record

> Superseded on 2026-08-09 by
> `docs/d3_06_reopening_batch_repairs.md`. In particular, the old F-02 snapshot
> mutation was removed and cannot be cited as current behavior.

Date: 2026-08-09. This record maps the first-scan findings to the owner-lane
implementation and focused evidence.

| ID | Repair | Evidence | Status |
|---|---|---|---|
| F-01 | Spawn-fence losers complete through the D2 executor with `pre_spawn_cancelled`, zero output, Receipt and budget settlement. | Focused runtime fence-loss test and D2 locked-executor tests. | ACCEPT |
| F-02 | `runs.snapshot_json.execution_phase=spawn_committed` is committed on the owner lane immediately before worker submission. | Runtime cancellation test waits for the durable phase. | ACCEPT |
| F-03 | Owner-lane watchdog writes `timeout_requested`; worker remains the process/timeout enforcer and terminal result writer. | Runtime bridge review and focused tests. | ACCEPT |
| F-04 | Deferred worker exceptions, including lost post-claim bridge context, reconstruct only the immutable fixture context and use D2 `_record_completion`, producing Receipt and exactly-once usage settlement before Run orphaning. | Focused worker-crash test plus recovery branch review. | ACCEPT |
| F-05 | Startup reconciliation scans running spawn-committed Actions and fail-closes them as effect-unknown/orphaned with Receipt and settlement. | `reconcile_stale_locked_runs`; owner-lane invocation during runtime start. | ACCEPT |
| F-06 | Locked grant identity is a versioned server-owned fixture namespace; browser requests carry no grant reference or policy material. | `_LOCKED_DEV_GRANT_NAMESPACE`, immutable fixture snapshot field. | ACCEPT with fixture-only scope |
| F-07 | StartRun rejects a contradictory `expected_revision`/`plan_revision` pair. | StartRun handler branch and command suite. | ACCEPT |
| F-08 | Close drains writers, then workers, then streams; writer timeout is surfaced and both executors close on error paths. | D3 runtime suite. | ACCEPT |
| F-09–F-12 | Prior repairs retained and rechecked. | OpenAPI, handshake, replay, CancelRun and fixture-args tests. | ACCEPT |
| F-13 | Added pre-spawn fence-loss, cancellation-after-spawn, worker-crash, and lost-owner-context recovery tests. | `tests.test_d3_06_journey_runtime` (6 tests). | ACCEPT |

Scope remains the frozen `python.unittest.locked` fixture. No general hostile
code sandbox, arbitrary shell, HTTP mutation expansion, or external publish was
introduced.
