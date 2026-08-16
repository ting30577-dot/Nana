# D3-06 reopening batch repair record

Date: 2026-08-09  
Status: local implementation repaired; independent implementation-exit review pending.

This record supersedes the implementation claims in
`docs/d3_06_batch_repairs.md`. It does not rewrite the historical first or
third no-edit scans. The implementation remains restricted to the exact T2
`python.unittest.locked` fixture.

## Third-scan findings

| ID | Repair | Evidence | Status |
|---|---|---|---|
| F-14 | Action terminal CAS, Receipt, output Artifact publication, provenance Relation, usage settlement, Action/Event/outbox and Run terminal state/Event now share one SQLite transaction. | Injected terminal-settlement failure rolls all facts back; recovery converges once. | repaired |
| F-15 | Startup reconciliation covers the historical terminal-Action/non-terminal-Run window and writes one missing Run terminal Event. | Historical-window restart test. | repaired |
| F-16 | The deterministic args Artifact is committed through the D1 content-addressed store and read through `ArtifactReader`; no synthetic `available` row remains. | Success/reopen/reader tests. | repaired |
| F-17 | Every locked result has a real `text/plain` Artifact, Receipt `after_artifact_ids`, producer binding, `run_produces_artifact` Relation and Relation Event/outbox. | Success and provenance assertions. | repaired |
| F-18 | The spawn fence is an append-only `action.output` Event/outbox fact; the frozen Run snapshot is never mutated. | Fence/restart tests and snapshot assertion. | repaired |
| F-19 | Browser `StartRunRequest` omits backend/capability; `to_canonical_command` injects the exact server-owned locked capability. | Request rejection and generated OpenAPI/client checks. | repaired |
| F-20 | Timeout intent, recovery groups and terminal completion now own explicit transaction boundaries. | Close/reopen and failure-injection tests. | repaired |
| F-21 | The focused suite now exercises real Artifact reads, close/reopen durability, persisted fence restart, historical repair and transaction rollback. | `tests.test_d3_06_journey_runtime` (17 tests). | repaired |

## Repair-time findings

These findings were discovered while validating the F-14 through F-21 repair
and were fixed before the final no-edit scan.

| ID | Finding and repair | Evidence | Status |
|---|---|---|---|
| F-22 | A rejected StartRun could provision the args Artifact before command validation. Provisioning now runs only after the request passes the immutable target/revision/fixture precheck. | Rejected StartRun has no Artifact side effect. | repaired |
| F-23 | Restart omitted paused cancel-pending, spawn-fenced Actions. Startup now classifies them conservatively as orphaned when termination cannot be re-confirmed. | Paused cancel-pending restart test. | repaired |
| F-24 | Proposed, authorized and claimed-without-fence restart windows were incomplete. They now converge without worker spawn or reclaim; claimed work releases its reservation once. | Three restart-window tests. | repaired |
| F-25 | Output producer/Relation facts could precede terminal settlement. Producer attachment, Relation/Event and Receipt linkage now occur inside the terminal transaction. | Rollback and provenance tests. | repaired |
| F-26 | Runtime exception recovery treated any surviving context as post-spawn uncertainty. Recovery now reads the durable spawn fence: no fence is pre-spawn cancellation; a fence is effect-unknown/orphaned. | Lost-owner-context-before-spawn test. | repaired |
| F-27 | A scheduler result other than `claimed` could fall through toward spawn. The bridge validates the claim result and reconciles budget-exhausted/non-claimed outcomes without spawning. | Budget-exhaustion/no-spawn test. | repaired |
| F-28 | Historical `effect_unknown` plus cancel intent could be downgraded regardless of the Action terminal reason. Reconciliation now requires the exact `cancelled_after_process_start` terminal reason; runner errors remain orphaned. | Historical runner-error/cancel-intent test. | repaired |
| F-29 | Gate-H audit facts lacked gate IDs, fixture/capability digests, effect decision and causation. Terminal settlement now appends Gate-A through Gate-H `action.output` decision Events with outbox rows in the same transaction. | Success audit asserts all eight gates and original command causation; crash audit asserts Gate-G rejection source. | repaired |
| F-30 | Receipt projection did not state the conservative billing basis required for uncertain effects. Projection now exposes deterministic `billing_basis`; terminal Action audit carries the same value. | Success and worker-crash projection assertions. | repaired |
| F-31 | A result Artifact could become canonically `available` before the terminal transaction. D3 now stages bytes off-database, then records staged metadata, promotes, publishes availability, attaches provenance and settles terminal facts inside one SQLite transaction. Rollback leaves no visible Artifact row; an orphan final blob is safely reused/quarantinable on recovery. | Injected rollback asserts zero staged/available result rows and successful idempotent recovery. | repaired |
| F-32 | Windows Job handle close failure and stream-reader non-termination were not reflected in `termination_failed`. Both now fail closed into Gate-G rejection and Run orphaning. | D2 process-tree regression plus strict D2/D3 suites. | repaired |

## Boundary retained

- No Approval or T3 export capability was registered.
- No browser-supplied test ID, backend, grant, effect declaration, shell text,
  network target or filesystem target was introduced.
- The worker receives no SQLite connection and performs no owner-lane writes.
- The watchdog records durable timeout intent; the locked D2 worker remains the
  process-timeout/termination authority.
