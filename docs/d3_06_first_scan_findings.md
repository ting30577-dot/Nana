# D3-06 first scan findings (no-edit scan)

Date: 2026-08-09. Scope: typed StartRun/CancelRun, runtime bridge,
journey command replay, D2 delegation, OpenAPI/handshake, shutdown, and the
new D3-06 tests. This is the consolidated scan list; repairs are intentionally
handled after the list.

| ID | Severity | Finding | Evidence / consequence | Decision |
|---|---|---|---|---|
| F-01 | P0 | Pre-spawn cancellation has no D2 release path. | Scheduler marks a claimed running Action as paused; the phased worker can observe cancellation before process creation, but current completion maps it to `effect_unknown` and records usage instead of a single pre-spawn cancellation/release. | VETO until D2 cancel-before-spawn settlement exists. |
| F-02 | P0 | Spawn fence is only an in-memory/implicit phase. | `actions.state='running'` means scheduler claim, not durable spawn commitment; crash/cancel between claim and worker start is not distinguishable. | VETO until owner-lane CAS fence is persisted in canonical facts. |
| F-03 | P0 | No independent owner-lane watchdog. | The worker runner owns timeout polling; the owner lane has no durable timeout intent writer that can reach a blocked worker. | VETO until watchdog intent and late-result arbitration are explicit/tested. |
| F-04 | P0 | Deferred bridge failures can leave incomplete Receipt/budget facts. | Runtime catch path only reconciles Action/Run state; admission failure, worker crash, or owner completion failure can lack Receipt/ledger exactly-once settlement. | VETO until one D2-owned recovery settlement path is used. |
| F-05 | P1 | `unknown_pending` recovery coordinator is not implemented. | The design requires deterministic effect_unknown/orphaned classification, but runtime has no restart/reconciliation scan for claimed/running work. | NOT CONSENSUS; implement before exit. |
| F-06 | P1 | StartRun provisions a PolicyGrant inside the journey writer. | The design calls for a configured server-owned grant reference; creating it ad hoc during a browser command risks mixing policy mutation with D3 orchestration. | NOT CONSENSUS; make fixture provisioning explicit and immutable. |
| F-07 | P1 | StartRun `expected_revision` is not bound to the requested Plan revision. | The handler validates `plan_revision` but ignores the command envelope revision, so stale browser commands can pass a contradictory revision pair. | VETO until the pair is checked. |
| F-08 | P1 | Shutdown lifecycle needs a full drain proof. | Worker tasks and owner-lane writers can depend on one another; the first implementation timed out `writers_empty`, and error paths did not always shut down the worker executor. | NOT CONSENSUS until orderly and crash shutdown tests pass. |
| F-09 | P1 | Handshake/OpenAPI initially advertised execution disabled and stale command union. | D3-06 exposes real T2 StartRun but the old handshake/schema still said execution was disabled / 11 commands. | ACCEPT after regenerated schema and handshake assertion. |
| F-10 | P1 | Command replay validator initially had no StartRun/CancelRun binding. | Replayed StartRun raised `KeyError`; CancelRun was not checked against its canonical Events. | ACCEPT after validator repair and replay tests. |
| F-11 | P1 | CancelRun initially called D2 scheduler inside the outer command transaction. | `RunSchedulerService` correctly rejects an already-active SQLite transaction; HTTP CancelRun therefore failed closed with an internal error. | ACCEPT after explicit D2 in-transaction entry point and test. |
| F-12 | P2 | The locked args Artifact has no general blob store. | D3 uses a server-owned immutable byte closure; this is safe for the frozen fixture but must be documented as a fixture-only loader, not a general artifact implementation. | ACCEPT with scope evidence; no generalization. |
| F-13 | P1 | Tests did not yet cover cancel-after-start, worker crash, or reconciliation. | Green success/replay tests alone cannot prove the D3-06 hard gates. | VETO exit until focused tests are added. |

The scan found no arbitrary shell/test-target input path in the typed browser
contract, and no UI success mutation was added. F-01–F-08 and F-13 remain open
for the batch-repair pass; F-09–F-12 are listed as repaired findings whose
repairs still require second-scan evidence.
