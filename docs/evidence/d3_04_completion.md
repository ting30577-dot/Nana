# D3-04 completion evidence

Date: 2026-08-08

Status: Codex ACCEPT; Claude ACCEPT on the supplied sanitized evidence; joint
D3-04 exit ACCEPT. D3-05 is authorized for design only.

## Scope proven

- The sole D3 FastAPI runtime serves only authenticated `/` and exact
  Vite-manifest assets in addition to the already accepted D3 read routes.
- The static build is checked for reparse/junction entries, forbidden route
  syntax, undeclared files, and source maps, then served from immutable bytes
  captured at startup. Anonymous known/unknown assets and documents fail closed.
- React obtains a canonical bootstrap and consumes authenticated SSE with
  `fetch + ReadableStream`; native `EventSource` is not used.
- The shared reducer preserves sparse Event IDs, exact duplicate fingerprints,
  aggregate/run sequences, literal stored states, streamed canonical IDs, and
  one bounded fresh-bootstrap recovery.
- The Cockpit/Studio exposes Workspace, Inquiry/provenance including Locator,
  Plan steps, locked-test Action, Activity, Artifact/Finding, Receipt result and
  usage, and literal `waiting_approval`/`effect_unknown`. The local Plan note is
  explicitly unsaved and disappears on reload.
- There is no human browser launch path, mutation route, Local Web bootstrap,
  Approval decision, Grant derivation, export, Tauri shell, or generalized
  sandbox claim in this stage.

## Review protocol and findings

The candidate was frozen for a no-edit full scan. That scan VETOed F1-F6;
batch repair followed. Final full re-review found F7, and normal-viewport visual
QA found F8. All F1-F8 resolutions and evidence are recorded in
`docs/d3_04_review_findings.md`. Codex's final local decision is ACCEPT.
Claude's exit review also ACCEPTed F1-F8 and found no new P0/P1 blocker. Claude
explicitly did not claim a raw-source/raw-log independent rerun; the normalized
response and two non-blocking matters without full consensus are recorded in
`docs/claude_d3_04_exit_response_sanitized.md` and
`docs/d3_04_decision_record.md`.

## Final executable evidence

- Python 3.12.13 `compileall nana_sidecar tests scripts`: pass.
- Full Python unittest: 306 tests OK, 1 existing skip.
- D3 Workspace/runtime/read-model under `ResourceWarning-as-error`: 37 tests OK,
  1 existing skip.
- TypeScript strict check: pass.
- Vitest: 23 tests OK across projection, SSE, and store suites.
- Shared reducer self-test: pass.
- Vite production build: pass, no source map, content-addressed JS/CSS.
- System Chrome 150 real-browser E2E: 11 tests OK, zero test retries.
- E2E covers reload/local-draft discard, known-asset default deny, exact
  Authorization/Origin/Last-Event-ID, four automatic reconnects plus successful
  manual reconnect, 401 terminal session expiry, two-attempt bootstrap transport
  exhaustion, malformed parser and reducer recovery, sparse `10,12,19`, exact
  duplicate replay, fixture/token/build leakage scan, 200% text, exact 320 CSS
  px reflow, 125%/150% scale, forced colors, reduced motion, keyboard focus,
  axe serious/critical violations, and zero happy-path console errors.
- D0/D2 102-entry manifest self-check: pass; synchronized digest
  `6250ac3003dbe50fce45e16bb14a39b9f11b03eeaa23c72a6faac30eb946c682`.
- D3-04 immutable implementation manifest: 26 entries, zero mismatches; digest
  `e2abef890eb5d453c347c18af47c7fa6eeadf1b500af819554251cbb66b5eaa6`.
- `git diff --check`: no whitespace error; only existing LF/CRLF conversion
  warnings in unrelated/earlier files.
- Privacy scan for usernames, absolute user paths, private-key markers, API-key
  markers, and long Bearer literals in the D3-04 package: zero matches.

## Known bounded observation

The full Python process still emits the pre-existing GC uncollectable-object
ResourceWarning at interpreter shutdown. The strict 37-test D3 lock/runtime/
read-model gate passes with ResourceWarning promoted to error, so there is no
evidence that this warning involves the D3 handle, process, SQLite, write, or
static serving path. D3-04 does not open mutation serving.
