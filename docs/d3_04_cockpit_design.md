# D3-04 read-only React Cockpit/Studio design

Date: 2026-08-01
Status: Codex independent proposal; no UI implementation yet

## Goal and non-goals

D3-04 makes the D3-03 canonical projection understandable in a real browser.
It adds no command writer, SQLite write, Action proposal, authorization or
Approval inference, retry, export, Tauri shell, or alternative HTTP authority.
Every terminal/result/status label is a literal stored fact or a reducer-derived
transport state; the browser never invents success.

## Serving and session boundary

The D3-02 FastAPI runtime remains the sole HTTP authority. It adds an
**authenticated static UI surface** only after explicit review: `GET /` and
an explicit allowlist of content-addressed build assets require the same exact
Host, Origin, and Bearer LocalSession checks as API requests. They are not
public/bootstrap routes. There is no index fallback, catch-all asset handler,
source-map serving, or unauthenticated `200` response.

For browser E2E, a test launcher creates an in-memory LocalSession and uses
Playwright `extraHTTPHeaders` for document, asset, fetch, and stream requests.
The runtime injects no token into HTML, URL, storage, logs, or build artifact.
The React session token exists only in Playwright request headers for this
development slice. Same-origin API URLs are derived from `window.location`, so
there is no UI-config endpoint.

D3-04 explicitly has **no human top-level browser launch path**. A normal
navigation cannot supply the required Bearer and exact Origin headers. It is a
real-browser, authenticated technical slice driven by the E2E launcher, not a
Local Web fallback or production desktop launcher. The authority-spec Local Web
Plan B (one-time 256-bit fragment bootstrap and session exchange) is a separate
security gate and is not silently introduced here.

## UI architecture

`nana_web` gains Vite + React + TypeScript and a production build written to a
runtime-owned static directory. The app has one `ProjectionStore`:

1. `fetch('/api/v1/bootstrap', Authorization)` obtains the canonical snapshot.
2. It builds state solely with `projectionFromBootstrap`.
3. It opens `fetch('/api/v1/events', Authorization, Last-Event-ID)` and parses
   SSE frames with `ReadableStream`; native `EventSource` is prohibited.
4. Every Event is applied by `applyProjectionEvent`. A reducer or parser error
   freezes the cursor, labels the view `refresh required`, cancels the stream,
   and performs exactly one fresh-bootstrap recovery before reconnect. If that
   bootstrap is malformed/invalid, or its own request fails after its bounded
   retry budget, the store enters visible terminal `projection unavailable` and
   requires a new launcher session; it never loops bootstrap recovery.
5. On a retryable transport loss it performs capped exponential backoff with
   jitter, reconnecting with the stored canonical cursor. It has no integer gap
   oracle. At the retry ceiling it enters literal `stream disconnected` state;
   a user-initiated read-only reconnect is allowed, but the test runner itself
   has no retry and must record the failed run.
6. All bootstrap, stream, and retry operations are owned by one monotonic
   generation and one single-flight controller. Bootstrap has priority: it
   aborts the active stream and clears a reconnect timer; a transport failure
   while bootstrap is pending is folded into that bootstrap's bounded retry
   budget and cannot start a second stream. A `401`/`403` or other session-reset
   indication is terminal `session expired`: it does not back off or invent a
   token; the E2E launcher must create a new session. Refresh/disconnect/
visibility restoration always rebuild from bootstrap then
   replays `id > high_water`; local selection and draft notes are explicitly
   non-canonical and cannot change displayed domain status.

The transport policy is frozen: a stream gets at most **four** automatic
reconnect attempts, with nominal delays `250, 500, 1000, 2000 ms`; each delay
uses a uniform ±20% jitter and 2000 ms is the cap. Each initial or recovery
bootstrap gets at most **two** transport attempts (one request plus one retry)
under that same delay policy (the second attempt uses the first `250 ms` delay);
exhaustion enters terminal `projection unavailable`. The E2E test runner still
has zero test retries. The store receives delay/clock/random dependencies only
at construction time, never by capturing global timers at module load.

The deterministic test seam is fixed: Playwright calls
`browserContext.addInitScript` to place a test transport override on the page
global before **any** application module executes. It is DevTools-level page
injection, not a served JavaScript file, HTTP route, static asset, or manifest
entry. The React entry point reads and validates that optional override only
when it constructs the store; absent a valid override it constructs the real
browser delay/clock/random dependencies. Production bundle tests load without
the init script and assert the real dependency path is selected. The override
only resolves local delay promises and supplies a fixed jitter value; it cannot
change headers, Authorization, request URLs, payloads, responses, or server
behavior. It enables deterministic fourth-stream-failure, second-bootstrap-
failure, and retryable-to-terminal aria-live assertions without wall-clock
waits.

Deterministic failures come from a separate test-orchestration layer, not from
the timing override or real network instability. Playwright `page.route` matches
only the already-constructed same-origin bootstrap or SSE request and aborts
the response/connection for an exact counted attempt. It observes and asserts
the original URL and Authorization/Origin/Last-Event-ID headers before aborting;
it never rewrites those request fields or serves a replacement payload. Thus it
does not alter the runtime server, production bundle, canonical payload, or
authorization semantics. Combined with the fake delay, it proves four stream
failures reach terminal disconnect and two bootstrap transport failures reach
`projection unavailable`. The timing override itself never changes server
behavior; the external E2E orchestration only controls connection lifecycle.

Parser/reducer negative tests use a second, explicitly narrower Playwright-only
orchestration mode. After it has asserted the original request fields, a
`page.route` handler may fulfill that browser request with a deliberately
malformed SSE frame or a syntactically valid Event that violates reducer
watermarks. This is the only test mode allowed to synthesize a response body;
it exists solely inside the browser automation process, is not a sidecar route,
static asset, Vite manifest entry, or production fixture, and never changes the
outgoing Authorization/Origin/URL. It deterministically proves cursor freeze,
one fresh bootstrap, and `projection unavailable` after an invalid recovery
bootstrap. Transport-abort tests never fulfill a replacement body.

Each route script is bound to an expected store generation indirectly through
its observable request contract: it consumes a counted failure only when the
request has the expected path and exact `Last-Event-ID` cursor. Any unexpected
cursor or parallel matching request fails the E2E assertion rather than being
consumed. The test waits for each route observation before permitting the next,
which proves single-flight behavior and prevents route-counter races.

SSE parser requirements: UTF-8 decoding with stream mode; CRLF/LF handling;
multi-line `data`; only numeric `id`; no cursor advance for malformed frames;
the server event type and JSON payload must form the D3 `ProjectionEvent`; abort
on untrusted/malformed envelope and refresh. Reconnect is single-flight,
aborted during a fresh bootstrap, and uses no automatic mutation.

## Product surface

The visual direction is an industrial/editorial research control room: ink,
warm paper, oxidized orange warning accent, dense ruled causality rail, and
serif section labels paired with a readable humanist sans. Reduced-motion mode
removes all rail animation. The central causality rail is memorable but never
the only information carrier.

- **Cockpit:** workspace lifecycle, literal Active/Needs You/Running/Failed
  counters, connection status, and accessible negative-state banners.
- **Studio:** provenance panel (Inquiry/Resource/Locator/Claim/Evidence), Plan
  revision and steps, Run/Action/Receipt trace, Artifact/Finding trace, and
  bounded Activity feed.
- **Causality rail:** IDs and relation labels connect Plan step → Action → Event
  → Artifact/Finding → Receipt. Missing relationships are shown as `not
  recorded`, never guessed.
- `waiting_approval`, `cancelled`, `orphaned`, `budget_exceeded`, and
  `effect_unknown` retain literal wording. `effect_unknown` has a quarantine
  banner with no local retry/resume/dismiss/mark-success control.
- An optional local Plan-note editor is clearly labelled `local draft — not
  saved`; it never alters the canonical Plan view and its state is discarded on
  reload.

## Accessibility and tests

The runtime derives the static allowlist from the Vite production manifest on
startup, validates every referenced file is a regular descendant of the build
root, and rejects the startup if a manifest entry is malformed or a source map
is emitted. It verifies every declared manifest file exists and every eligible
build asset is declared exactly once. It serves only `index.html` plus
manifest-referenced assets; even an authenticated request for any other asset
returns rejection.

The UI uses semantic landmarks, keyboard-visible focus, logical tab order,
status `aria-live` regions, text labels in addition to color, and no focus trap.
On fresh bootstrap it deterministically moves focus to the labelled projection
status heading (and announces the refresh); it never silently drops keyboard
focus. Retryable reconnect and terminal disconnect have distinct exact
`aria-live` messages, asserted by browser tests.
Browser tests cover 125%/150% DPI plus WCAG 1.4.4 at 200% text zoom and 1.4.10
at 320 CSS px/400% reflow, keyboard-only navigation, reduced motion and
`prefers-contrast`, status/error screen-reader announcements, contrast checks,
normal/negative states, reload, sparse `10,12,19` events, exact duplicates,
disconnect/reconnect, terminal session reset, malformed stream refresh, and
  fixture absence from production routes/build navigation. Tests inspect outgoing
headers to prove `Authorization` is supplied by fetch/ReadableStream and that
no `EventSource` is used. They assert every document, asset, unknown static
path, source map, and any removed config route rejects unauthenticated access.
They also assert forced-colors usability and that a 401 body/header never echoes
the submitted Authorization value.

## Security decisions proposed

- Authenticated static routes: ACCEPT only for this test-only Web slice,
  subject to Claude review; anonymous root/assets and all static fallbacks are
  VETO.
- Token in URL/query/hash/localStorage/sessionStorage/build output: VETO.
- Native EventSource: VETO.
- Browser state as canonical or a source of authorization/terminal success:
  VETO.
- Fixture navigation/API/auth mode in production UI: VETO.

## Entry/exit evidence

Entry: D3-03 joint ACCEPT and its 303-test evidence.

Known intentional path split: D3-04 authenticates only the E2E browser via
test-launcher headers. Future Local Web Plan B would inject credentials through
its separately gated one-time bootstrap and is therefore not proven by D3-04;
the current UI is deliberately not human-navigable until that security decision.

Exit requires real-browser read-only reload/reconnect/negative-state coverage,
accessibility and DPI checks, runtime route/default-deny re-review, TypeScript
and Python regressions, static artifact token scan, a no-edit full scan,
consolidated findings and repairs, and Claude exit ACCEPT.
