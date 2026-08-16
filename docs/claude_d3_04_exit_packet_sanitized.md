# D3-04 exit review packet (sanitized)

This packet contains only relative modules, contract facts, test counts, safe
software versions, and synthetic identifiers. It contains no username,
absolute path, hostname, network identifier, token value, environment value,
credential, license, or raw log.

## Frozen scope

D3-04 is an authenticated E2E-only read bridge from D2/D3 canonical facts to a
minimal React Cockpit/Studio. It has no human top-level launch path. It adds no
mutation method, Local Web bootstrap, UI config route, PolicyGrant/Approval
query or derivation, Action proposal, export, publish, Tauri shell, or broad
sandbox claim. Playwright supplies the test LocalSession headers; no credential
is embedded in HTML, URL, storage, source, manifest, or production bundle.

## Implemented boundary

- `runtime_app`: optional `/` plus manifest-declared static routes remain behind
  the exact Host/Origin/Bearer gate. Root, metadata directory, every asset path,
  and every disk entry reject links, Windows reparse points, and junctions.
  Manifest route syntax is conservative; source maps, undeclared files,
  fallback paths, and duplicate declarations reject startup. Validated index
  and asset bytes/media types are captured once at startup and later file
  replacement cannot change served content.
- `projection`, `sse`, `store`: bootstrap collections/status/IDs/watermarks fail
  closed; Event IDs, aggregate versions, and run sequences are positive safe
  integers; sparse global IDs are legal; exact duplicate fingerprints are
  idempotent; conflicts/decreasing/sequence errors freeze cursor. SSE is UTF-8
  stream-decoded with CRLF/LF and multi-data support. Stream uses fetch plus
  ReadableStream. A parser/reducer error gets one fresh bootstrap only. Stream
  transport gets four automatic reconnect attempts with 250/500/1000/2000 ms
  nominal delay, uniform plus/minus 20 percent jitter and 2000 ms cap. Manual
  reconnect owns a new generation/controller and resumes the frozen cursor.
  401/403 is terminal session expiry.
- `App`: literal stored Workspace/Needs You/Run/Action/Artifact/Finding/Receipt
  states only. Locator, Plan step, locked test capability, producer/evidence,
  Receipt result/usage, and canonical relation keys are visible. Stored
  `waiting_approval` is shown without reading Approval. `effect_unknown` is
  quarantined with no retry/resume/dismiss/mark-success control. Local Plan text
  is labelled unsaved, cannot change canonical state, and is discarded on
  reload.
- Browser orchestration modes remain separated by test: timing injection only
  changes delay/random; transport mode only aborts counted requests; parser/
  reducer mode alone synthesizes invalid response bodies. Every counted request
  asserts exact URL, Authorization, Origin, and cursor before orchestration.

## Required no-edit review protocol

Codex froze the candidate and performed a complete no-edit scan before writing
the consolidated findings. Candidate decision was VETO:

- F1 P0: manual reconnect reused a cleared controller and could not send.
- F2 P1: static root reparse evidence was lost and FileResponse had a serving
  time-of-check/time-of-use gap.
- F3 P1: browser security/recovery evidence was incomplete.
- F4 P1: Locator/Plan step/test/Receipt relations were missing from the product
  surface.
- F5 P1: malformed bootstrap values were accepted and streamed IDs were lost.
- F6 P2: clean-workspace test scripts and generated output hygiene were not
  reproducible.

All six were batch repaired. The final full review then VETOed F7 (zero-valued
sequence acceptance, optional sparse replay observation, Finding rail
selection, stale static type annotation). Visual QA VETOed F8 (empty Studio
grid slab and a happy-path console 404). F7/F8 were repaired and all complete
gates were rerun. Codex now marks F1-F8 ACCEPT and D3-04 locally ACCEPT.

## Evidence

Safe software versions: Python 3.12.13, Node.js 24.15.0, npm 11.12.1, system
Chrome 150.0.7871.187.

- compileall: pass.
- full Python unittest: 306 OK, 1 existing skip.
- D3 Workspace/runtime/read-model with ResourceWarning as error: 37 OK,
  1 existing skip.
- TypeScript strict: pass.
- Vitest: 23 OK; shared reducer self-test: pass.
- Vite production build: pass; no source map.
- real-browser E2E: 11 OK, retries zero.
- E2E explicitly proves reload, draft discard, known-asset denial, authenticated
  removed-config 404, submitted credential absent from 401 body/headers, exact
  request headers, terminal disconnect and successful manual reconnect, session
  expiry, bootstrap exhaustion, parser/reducer one-bootstrap recovery, sparse
  10/12/19 plus exact duplicate, production leakage absence, accessibility,
  reflow/scale, forced colors/reduced motion, focus, axe and clean console.
- D0/D2 102-entry manifest: zero mismatches; synchronized digest recorded in
  the local evidence summary.
- D3-04 implementation manifest: 26 entries, zero mismatches; digest recorded
  in the local evidence summary.
- full-suite shutdown still has the pre-existing GC ResourceWarning. The D3
  strict gate passes, so it is not evidenced in D3 lock/runtime/read-model
  handles or writes. D3-04 serves no mutation.

## Requested independent decisions

Please independently review and return:

1. F1 through F8: ACCEPT or VETO each, with any counterexample.
2. Static authenticated allowlist/preload boundary: ACCEPT or VETO.
3. Store reconnect/recovery/session state machine: ACCEPT or VETO.
4. Canonical-fact UI/non-canonical draft boundary: ACCEPT or VETO.
5. Browser/security/accessibility evidence sufficiency: ACCEPT or VETO.
6. Overall D3-04 implementation exit: ACCEPT, VETO, or not yet consensus.
7. Whether D3-05 design work may begin while all D3-04 scope exclusions remain
   frozen.
