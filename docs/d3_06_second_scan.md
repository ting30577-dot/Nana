# D3-06 second scan (no-edit review)

> Superseded on 2026-08-09 by `docs/d3_06_third_scan_findings.md`, the reopening
> repair batch and `docs/d3_06_final_scan.md`. The ACCEPT below is historical
> and must not be used as the current implementation-exit verdict.

Date: 2026-08-09. This scan was repeated after the fence-loss repair and its
focused test. It re-read the runtime bridge, Journey command writer,
D2 locked executor/scheduler, tests, and the checked-in OpenAPI contract.

## Hard-gate result

- Workspace lock and owner-lane SQLite writes remain inherited from D2; the
  worker receives immutable fixture arguments and no database handle.
- Admission, scheduler claim, Receipt, budget usage and terminal projection
  still delegate to D2 services. The bridge adds only the durable spawn CAS and
  owner-lane intent/recovery coordination.
- Cancellation before spawn is a D2 completion with a zero-effect Receipt;
  cancellation after spawn is conservatively effect-unknown. A watchdog writes
  timeout intent but does not synthesize a terminal success/failure.
- A failed spawn-fence CAS cannot reach the worker and still maps through the
  D2 completion transaction to a cancelled Receipt and zero-effect settlement.
- Worker exceptions and startup stale-run reconciliation use the same completion
  settlement path, then orphan the Run. The browser cannot select a capability,
  test id, grant, or policy material.
- If the owner-lane bridge loses its in-memory context after claim, it rebuilds
  only the immutable locked fixture context and re-enters the same completion
  path; unrelated capability Actions are excluded from startup reconciliation.
- Shutdown sequencing is explicit and a writer drain timeout is surfaced rather
  than silently closing SQLite.

## Residual caveats

The implementation is intentionally fixture-only. `unknown_pending` is represented
by the durable `spawn_committed` phase plus owner-lane recovery rather than by a
new public Run enum, preserving D2 schema compatibility. No general sandbox or
blob-store claim is made.

## Verdict

Codex second scan: ACCEPT, with the fixture-only caveat above. The sanitized
implementation-exit packet was prepared, but Claude could not be reached: the
configured gateway returned Windows socket permission error 10013 in the local
execution environment, and the controlled network retry was rejected by the
security policy. Joint implementation-exit status is therefore **尚未达成共识**;
D3-07 is not started.

Focused evidence after this scan: D3-06 runtime 6 tests OK; strict D3 suite 96
tests OK with 2 skips; full Python suite 359 tests OK with 2 skips; compileall,
frontend typecheck, manifest verification, and diff check all pass.

Blocker update: a third ordinary Claude adapter retry produced the same
Windows socket permission error. See `docs/d3_06_claude_exit_blocker.md`.
