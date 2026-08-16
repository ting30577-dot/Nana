# Claude review packet - D3-06 implementation exit (sanitized, reopened)

Date: 2026-08-09  
Requested decision: `ACCEPT`, `VETO`, or `NOT YET CONSENSUS`.

This packet contains repository-relative paths only. It contains no user or
machine identity, absolute path, credential, endpoint, environment value or
secret. Please review only; do not modify files.

## Exact scope

D3-06 is limited to the exact T2 `python.unittest.locked` development fixture.
It does not authorize Approval, T3 export, arbitrary shell/Python, arbitrary
test selection, network access, hostile-code sandbox claims, browser-supplied
authorization/effect declarations or Workspace-outside writes. D3-07 remains
disabled regardless of local test status until this review and its separate
07-00 joint security gate both ACCEPT.

The earlier local implementation ACCEPT was withdrawn after a new no-edit scan
found F-14 through F-21. Those findings and F-22 through F-32 discovered during
repair are recorded in `docs/d3_06_third_scan_findings.md` and
`docs/d3_06_reopening_batch_repairs.md`. The current local verdict comes from a
new final no-edit scan, not from the superseded packet.

## Implemented boundary

### Browser and fixture authority

- `StartRunRequest` contains only command/target/revision/random-seed fields.
  It has no backend, capability, test ID, grant, policy, effect, shell, network
  or path field.
- `to_canonical_command` injects the exact server-owned
  `PYTHON_UNITTEST_LOCKED_CAPABILITY`.
- Invalid target/revision/fixture requests are rejected before args Artifact
  provisioning.
- The deterministic args Artifact is committed through the D1
  content-addressed store. D2 preflight reads it with `ArtifactReader`, verifies
  state/media/hash/size, and binds the same canonical bytes to
  `ActionHashMaterial`.

### Owner-lane bridge and lifecycle

- Owner lane: D2 admission, durable authorization, scheduler claim and budget
  reservation.
- Owner lane: append-only `action.output` + outbox spawn fence. The immutable
  Run snapshot is never mutated.
- Worker: only the frozen D2 process segment, immutable test ID/root/limits and
  a thread-safe cancel callback; no SQLite connection or database write handle.
- Owner lane: completion/recovery is the only terminal writer. The timeout
  watchdog records durable `timeout_requested`; the D2 worker enforces process
  timeout and termination.
- A scheduler result other than the exact claimed Action fails closed before
  spawn. Pre-spawn cancellation settles zero effects; post-fence cancellation,
  runner failure and termination uncertainty are conservative.

### Atomic terminal visibility

For a result, bytes are first staged only in the private Artifact-store staging
area. Inside one `BEGIN IMMEDIATE` transaction the owner lane:

1. records staged Artifact metadata/Event/outbox;
2. performs same-volume content-addressed promotion and publishes `available`;
3. binds `producer_run_id` and inserts the `run_produces_artifact` Relation and
   Relation Event/outbox;
4. terminal-CASes the Action and inserts its Receipt with the exact output
   Artifact ID;
5. records measured usage and decrements the unique reservation once;
6. appends Gate-A through Gate-H audit Events and the terminal Action Event;
7. terminal-CASes the Run and appends its terminal Event/outbox.

An injected failure after steps 1-6 but before Run settlement rolls the entire
SQLite fact set back: no Receipt, no staged/available result Artifact row, no
producer/Relation, no Gate decision Event and no terminal Action/Run Event are
visible. A promoted orphan blob is content-addressed and is safely reused (or
eligible for D1 orphan reconciliation) during the next recovery attempt.

### Gate-G / Gate-H and billing

- The locked process path kills the process tree on cancel/timeout/output cap,
  confirms the worker exit, joins stdout/stderr readers and closes the Windows
  kill-on-close Job. Reader non-termination, process-tree termination failure
  or Job close failure sets `termination_failed` and cannot become success or
  cancelled.
- Each terminal D3-06 Action writes append-only/outboxed Gate-A..H decision
  Events with gate ID, fixture digest, capability digest, effect decision,
  decision source, actor and original command causation. Gate-G records
  termination/liveness evidence and rejects runner-liveness uncertainty.
- Receipt projection exposes deterministic `billing_basis`:
  `measured_observed_effect`, `not_charged_pre_spawn`, or
  `conservative_uncertain_effect`. The Action terminal audit records the same
  basis. Uncertain effects are never silently refunded or reported as success.

### Restart convergence

Startup reconciliation handles these persisted single-Action locked windows:

- proposed/authorized before claim: cancel, never re-admit or reclaim;
- claimed/running without spawn fence: pre-spawn cancel Receipt and one
  reservation release;
- spawn-fenced running: effect-unknown Receipt and orphaned Run; never rerun;
- paused cancel/timeout intent plus spawn fence: conservative terminal result;
- terminal Action/Receipt plus running/paused Run from historical code: repair
  the missing Run terminal fact once;
- terminal Run plus unstarted Action: add the missing Action cancellation fact.

Historical reconciliation only maps an effect-unknown Action to cancelled when
its terminal Action Event proves `cancelled_after_process_start`; a
`runner_error` cannot be downgraded merely because cancel intent also exists.

## Evidence

- `tests.test_d3_06_journey_runtime`: 17 tests, pass. Coverage includes browser
  backend rejection, success/provenance/ArtifactReader, command replay,
  pre-spawn fence loss, post-spawn cancel, worker crash, lost context, budget
  exhaustion/no spawn, close/reopen durability, each restart window, historical
  repair, Gate-A..H audit/causation/billing, and injected transaction rollback.
- D1 Artifact commit/failure/reconciliation plus D3-06: 51 tests, pass.
- D3 strict `-W error::ResourceWarning`: 107 tests, 2 declared platform skips,
  pass.
- D2 strict `-W error::ResourceWarning`: 55 tests, pass.
- Full Python: 372 tests, 2 declared platform skips, pass. The only shutdown
  warning is the previously attributed legacy PySide6 test-double cycle; it is
  absent from strict D2/D3 suites.
- Python compileall: pass.
- TypeScript strict check: pass.
- Frontend Vitest: 23 tests plus projection self-test, pass.
- Frontend production build: pass.
- D0 manifest verification: pass after the frozen-source hash refresh.

## Requested strict review

Please independently determine whether any concrete P0/P1 implementation
blocker remains for the exact D3-06 scope. In particular, review:

1. atomic Artifact/Receipt/Relation/budget/Action/Run visibility and rollback;
2. claim/spawn/cancel/timeout/crash/restart classification and exactly-once
   settlement;
3. Gate-G cleanup failure semantics and Gate-H audit completeness;
4. server-owned fixture/browser boundary and absence of capability broadening.

Return an explicit `ACCEPT`, `VETO`, or `NOT YET CONSENSUS`, followed by concise
evidence and any mandatory repair. Do not infer that D3-07 is authorized by a
D3-06 verdict.
