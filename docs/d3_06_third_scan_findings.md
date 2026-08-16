# D3-06 third scan findings (no-edit reopening scan)

Date: 2026-08-09  
Status: local VETO; the earlier local ACCEPT is superseded.

This scan was performed after the handoff package was independently re-read
against authoritative specifications 05, 06, 07, 11 and 12. No runtime file
was edited before this consolidated finding list was completed. D3-07 remains
disabled.

| ID | Severity | Finding | Evidence / consequence | Decision |
|---|---|---|---|---|
| F-14 | P0 | D3 terminal Run state and Run Event are not committed with the D2 Action/Receipt/budget completion transaction. | `LockedUnittestExecutorService._record_completion` commits the terminal Action, Receipt, usage and Action Event. `JourneyCommandService.complete_locked_action` then updates the Run and appends its Event outside an explicit transaction. A close/crash can roll that second part back, leaving a terminal Action/Receipt with a `running` Run. | VETO until one transaction owns the complete terminal fact set and response-loss/reopen evidence proves it. |
| F-15 | P0 | Startup reconciliation does not cover the terminal-Action/running-Run crash window. | `reconcile_stale_locked_runs` selects only `runs.state='running' AND actions.state='running'`. It cannot repair the F-14 state, despite the previous exit evidence claiming crash/restart convergence. | VETO until restart reconciliation is idempotent for both pre-completion and post-Action/pre-Run windows. |
| F-16 | P0 | The canonical args Artifact is marked `available` without a D1 content-addressed blob. | `_start_run` inserts an `artifacts` row directly and the executor receives bytes from an in-memory closure. `ArtifactReader` cannot prove the row readable from the Workspace store, violating the Artifact visibility/commit protocol. | VETO; fixture-only scope does not permit a false canonical `available` fact. |
| F-17 | P0 | The required locked-test result Artifact and Receipt linkage are absent. | The successful worker result creates no D1 committed output Artifact; `action_receipts.after_artifact_ids_json` remains empty. The frozen Plan explicitly expects a `text/plain test result`. | VETO until success/failure evidence uses the D1 store and the Receipt identifies the exact produced Artifact. |
| F-18 | P1 | The durable spawn fence mutates the frozen Run snapshot and has no Event/outbox audit fact. | `commit_spawn_fence` adds `execution_phase` to `runs.snapshot_json`. Authoritative specification 05 freezes Run inputs/snapshots; the phase change is operational state, not frozen input. No append-only Event records the fence. | VETO the current representation; use an append-only canonical fence fact without changing the snapshot. |
| F-19 | P1 | The browser request still supplies a capability/backend reference. | `StartRunRequest.backend` is posted by the browser and copied into the canonical command, while the accepted D3-06 boundary says the server exclusively selects the frozen capability and the browser supplies no capability material. Exact-value rejection narrows risk but does not satisfy the interface boundary. | VETO until the browser-safe request omits backend and the server injects the frozen reference. |
| F-20 | P1 | Timeout intent and several recovery writes have no explicit commit boundary. | `request_locked_timeout`, the Run half of `complete_locked_action`, and fallback branches of `reconcile_locked_failure` issue DML/Event writes without owning a transaction. Same-connection tests can observe these uncommitted facts and mask close/reopen rollback. | VETO until every owner-lane fact group is explicit, atomic and reopened in tests. |
| F-21 | P1 | The prior focused suite does not exercise the claimed startup recovery path or reopen durability. | The six D3-06 tests cover same-process success, replay, cancellation, worker exception and a direct recovery helper. None closes/reopens SQLite after completion, invokes real startup reconciliation on a persisted spawn fence, or reads produced blobs through `ArtifactReader`. | VETO the old evidence strength; add failure-injection/reopen/reader tests before a new local verdict. |

## Scan conclusion

The prior D3-06 local ACCEPT and its sanitized exit packet are stale. The
authorized D3-06 design remains the implementation boundary, but implementation
exit is locally VETOed until F-14 through F-21 are repaired in one batch,
followed by focused/full verification and a second no-edit scan. No Approval,
T3 capability, external path selection, or Workspace-outside write is
authorized by this reopening.
