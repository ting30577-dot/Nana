# D3-09 and v0.3.0-dev-D3 final Codex-only acceptance

> Historical acceptance. Current authority: [`CURRENT_D3_AUTHORITY.md`](CURRENT_D3_AUTHORITY.md).

Date: 2026-08-13  
Decision: **ACCEPT** (effective after the final manifest-backed full suite)

> Superseded for current product-exit status later on 2026-08-13. This ACCEPT
> remains a historical scoped snapshot, but did not exercise a normal-user
> credential bootstrap, general Pause/Resume or failed→retry_of. The live
> launcher/security repair requires a new manifest-backed release gate before
> D3 can be accepted again.

## Outcome

Nana D3 now proves the requested minimal React vertical journey:

`create -> provenance -> editable Plan -> locked T2 Run -> Activity -> Artifact
-> Finding draft -> one-time Approval -> controlled T3 draft export -> Receipt`

The successful browser test performs every step through visible typed controls.
It validates the exact narrow request bodies, reloads after export and waits for
canonical Receipt facts. Ten consecutive executions each started a new
temporary Workspace/runtime and one-use export selection. All ten passed in
order with Playwright `retries=0`.

## Requirement evidence

| Requirement | Direct current evidence | Decision |
|---|---|---|
| Workspace owner/lock/readiness | D3-01/02 tests and 204-test strict gate | proven |
| sole authenticated runtime/OpenAPI authority | runtime authority tests, anonymous-route and session E2E | proven |
| canonical bootstrap/SSE/replay | Python read-model tests, 33 projection + 14 SSE tests, 17 browser baseline | proven |
| core typed mutation UI | 2 isolated mutation journeys including response loss/conflict/cancel | proven |
| locked T2 execution | real worker path in full journey, worker crash and owner-context-loss browser cases | proven within exact fixture-only scope |
| canonical Activity/Artifact/Finding | full journey and evidence rail/read-model tests | proven |
| one-time Approval | approved/denied/expired/concurrent/replay Python tests and browser matrix | proven |
| controlled external draft | interactive launcher authority test, path matrix, fixed renderer/canaries, browser success | proven for exact fixed-local public draft |
| Receipt/effect uncertainty | canonical Receipt reload, post-fence effect_unknown quarantine, no-retry controls | proven |
| ten consecutive E2E | `scripts/run_d3_ten_success.mjs`: 10/10, new runtime per run, retries=0 | proven |
| failure matrix | 25/25 release browser cases: reconnect/session/stream, response loss, cancel, denied, expired, worker crash, owner loss, export uncertainty | proven |
| evidence/manifests | final scoped manifests plus D3 final manifest; zero missing/hash/digest errors | proven after final refresh |

## Verification snapshot

- compileall `nana_sidecar tests scripts`: pass
- strict D2/D3 `ResourceWarning`: 204 pass, 2 declared platform skips
- full Python: 412 pass, 2 declared platform skips after manifest refresh
- TypeScript check: pass
- Vitest: 67 pass; projection self-test: pass
- production Vite build: pass
- ten consecutive complete browser success journeys: 10/10, retries=0
- complete browser release/failure matrix: 25/25, retries=0
- all live scoped and final D3 manifests: zero errors

The full Python process still emits the previously attributed legacy PySide6
GC-shutdown ResourceWarning after `OK`. The strict D2/D3 process/handle/write
suite promotes ResourceWarning to error and passes; this is not evidence of an
open D3 execution/export handle path.

## Scope statement

This ACCEPT does not claim a hostile-code sandbox. D2/D3 locked execution is a
trusted frozen `python.unittest.locked` fixture path. It does not authorize
arbitrary shell/Python, network, generic HTTP mutation, T4 PublishExport,
remote publish, path entry in the browser, overwrite, retry/rebind after
uncertainty, or any broader external effect.

Historical Claude/transport records remain historical. No Claude call or retry
occurred in this completion run and no historical non-verdict was relabelled.
Codex independently designed, implemented, reviewed, tested and accepted D3
under the product owner's explicit governance decision.
