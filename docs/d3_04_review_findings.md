# D3-04 no-edit full-scan findings

Date: 2026-08-08
Review mode: candidate frozen; complete read-only scan before repairs
Candidate decision: **VETO**

The candidate passed its pre-scan checks, but passing checks were not treated as
exit evidence. The following consolidated findings cover implementation,
security boundary, product truth, browser behavior, and reproducibility.

## F1 — manual read-stream reconnect cannot start (blocker)

- Severity: P0.
- Evidence: `ProjectionStore.terminal()` aborts and clears the sole
  `AbortController`; `reconnect()` then calls `stream()` without creating a new
  controller. `stream()` returns immediately when the controller is null.
- Consequence: after the four automatic reconnect attempts, the visible
  `Reconnect read stream` control leaves the UI permanently in `reconnecting`
  and sends no request. The D3-04 exit journey is not completable.
- Required repair: manual reconnect must create a new generation/controller,
  remain single-flight, retain the frozen cursor, and be proven by a browser
  test that first reaches terminal disconnect and then reconnects successfully
  with the exact cursor and request headers.

## F2 — static build validation loses reparse evidence and has a serving TOCTOU

- Severity: P1 security.
- Evidence: `_validated_static_build()` resolves the supplied root before
  checking `is_symlink()`, does not reject reparse/junction directory components
  for `.vite` or `assets`, and stores paths that `FileResponse` opens later.
- Consequence: the passed root can be a link/junction without detection, and a
  validated index/asset can be replaced between startup validation and a later
  request. That weakens the claimed manifest-only immutable serving boundary.
- Required repair: reject link/reparse/junction components before resolution,
  validate a conservative static route alphabet, preload the validated index
  and assets as immutable bytes/media types at startup, and add root/component
  reparse plus post-validation replacement tests.

## F3 — browser security and recovery evidence does not meet the frozen design

- Severity: P1 evidence/behavior.
- Evidence: the suite does not perform a real reload, successful manual
  reconnect, UI-level 401/403 terminal transition, or two-attempt bootstrap
  transport exhaustion. Negative route handlers check `Last-Event-ID` but not
  exact URL/Authorization/Origin on every counted request. Anonymous denial is
  tested only for an unknown asset, authenticated absence is not shown for the
  removed config route, the 401 submitted credential is checked only against
  the body rather than headers, and fixture/test identifiers are not
  automatically scanned out of the production build. Backoff/jitter schedules
  and true multi-line SSE data also lack direct assertions.
- Consequence: Claude's conditional design checks and several D3-04 exit clauses
  are unproven; the current green E2E run can miss auth loss, route-mode drift,
  stale local state, or retry-budget regressions.
- Required repair: add exact shared request assertions, reload/local-draft
  discard, successful manual reconnect, session terminal, bootstrap exhaustion,
  known-asset default-deny, authenticated config 404, response-header no-echo,
  production-build leakage, retry/jitter, and multi-line SSE tests. Keep timing,
  abort, and synthesized-response modes mutually exclusive.

## F4 — the Cockpit/Studio omits required canonical facts and causal links

- Severity: P1 product completeness.
- Evidence: provenance omits `locators`; Plan rendering omits `steps`; Receipt
  rendering omits `result` and usage; the rail's first column contains only
  Actions, its Artifact/Finding column contains only Artifacts, and no displayed
  relation connects `plan_step_id`, `action_id`, `run_id`, producer Run, Finding,
  and Receipt. The fixture leaves `Needs You` at zero and does not prove a
  literal stored `waiting_approval` projection. No visible locked-test result is
  asserted.
- Consequence: the page is visually polished but does not yet prove that a user
  can understand the frozen dev journey from Plan step through test execution
  and evidence to Receipt. Parallel columns can imply causality without showing
  canonical keys.
- Required repair: display Locator, Plan steps, capability/test identity,
  Artifact/Finding producer/evidence links, Receipt result/usage, and literal
  relation keys; seed and assert stored `waiting_approval` without deriving
  Grant/Approval state. Preserve `effect_unknown` quarantine and local-draft
  non-canonicity.

## F5 — bootstrap/reducer validation is too permissive and streamed identities
are lost

- Severity: P1 correctness/future bridge.
- Evidence: `projectionFromBootstrap()` accepts arbitrary watermark value
  types, silently treats every non-`degraded` projection status as `ready`, and
  filters malformed collection rows instead of failing closed. `patchDomain()`
  creates newly streamed Run/Action/Artifact records with only a state, omitting
  their canonical `id` and relationship IDs.
- Consequence: a malformed recovery snapshot may be shown as ready until a
  later event happens to fail, while new streamed facts render as `not recorded`
  and cannot participate in the causal rail. This would immediately weaken the
  D3-05 bridge.
- Required repair: validate bootstrap status, collection shapes, watermark keys
  and positive safe-integer values; preserve IDs and event relationship fields
  when creating streamed domain records; add unit and real-browser assertions.

## F6 — clean-workspace test reproduction and generated-output hygiene are
incomplete

- Severity: P2 tooling/evidence.
- Evidence: `dist/` is ignored, but `npm run test:e2e` does not build first, so a
  clean checkout fails or a dirty checkout can test stale assets. `npm test`
  excludes the existing reducer self-test. Playwright's generated
  `test-results/` is not ignored. `nana_web/README.md` still says React has not
  started.
- Consequence: a green local result is not a single-command replayable stage
  gate, generated diagnostics pollute status, and the documented workspace
  state contradicts the implementation.
- Required repair: make frontend unit and E2E scripts include the reducer test
  and production build respectively, ignore generated Playwright outputs,
  remove only the diagnostics generated by this stage, and update the Web
  workspace instructions.

## Consolidated decision

- F1: VETO until repaired.
- F2: VETO until repaired.
- F3: VETO until required browser/security evidence exists.
- F4: VETO until the minimal canonical journey is understandable.
- F5: VETO until malformed bootstrap fails closed and streamed IDs survive.
- F6: ACCEPT only after reproducible scripts and output hygiene are fixed.
- Overall candidate: **VETO**. No item is marked accepted merely because the
  pre-scan test run passed.

## F7 — final re-review found residual contract/test selection gaps

- Severity: P1 correctness/evidence.
- Evidence: after the F1-F6 repair, SSE and bootstrap Activity validators still
  accepted zero Event IDs/aggregate versions/run sequences; the sparse browser
  test could finish before observing its second `Last-Event-ID: 19` request;
  argument Artifacts could fill the bounded Artifact/Finding rail before any
  Finding appeared; and the preloaded static asset list retained a stale `Path`
  annotation.
- Consequence: malformed zero-valued Events were not fully rejected, one replay
  assertion was timing-optional, and the causal surface could omit a required
  Finding despite one being canonical.
- Required repair: require positive Event sequence integers, wait for the exact
  second replay request, prioritize produced Artifacts and Findings before
  unproduced argument Artifacts, and correct the static asset type annotation.
- Decision: VETO until the narrow repair and complete gates pass.

## F8 — final visual QA exposed an empty-grid slab and console 404

- Severity: P2 product quality/browser hygiene.
- Evidence: the normal 1440px full-page screenshot showed the tall Execution
  list occupying only the first cell of a three-column Studio row, leaving two
  large rule-background cells with no content. The same clean navigation emitted
  one browser console 404 for an implicit static resource request.
- Consequence: the otherwise deliberate industrial/editorial surface looked
  unfinished, and the normal happy path did not have a clean browser console.
- Required repair: make the Execution trace a full-width responsive panel with
  bounded columns, declare a data favicon that adds no route or build asset, and
  assert zero console errors in the positive browser journey.
- Decision: VETO until visual recheck and browser gates pass.
