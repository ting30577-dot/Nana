# D3-04 design resolution packet (sanitized)

The prior review found three no-consensus items. Codex resolves them as follows:

1. Human navigation: D3-04 is explicitly a real-browser E2E technical slice
   only. It has no human top-level browser launch path because normal navigation
   cannot carry Bearer plus exact Origin. The separate Local Web Plan B security
   gate, including its one-time fragment bootstrap, remains out of scope.
2. Route/token scope: UI-config is removed. Static root and an explicit asset
   allowlist are authenticated; no anonymous document, fallback, source map,
   unknown asset, or config route returns success. The build/runtime injects no
   token into URLs, HTML, storage, logs, or static output.
3. State machine: retryable transport loss resumes from cursor with capped,
   single-flight jittered backoff; reaching the ceiling is a visible terminal
   disconnect. Malformed parser/reducer input freezes cursor and fresh-bootstraps
   once. 401/403/session reset is terminal and requires a new launcher session.
4. Accessibility: design now requires 200% text zoom, 320px/400% reflow,
   contrast/reduced-motion checks, status announcements, and focus preservation
   or deliberate focus transfer on refresh.

Codex decision: ACCEPT the revised design. Request Claude final design decision
before installing dependencies or implementing routes/UI.

## Mandatory closure amendments after second review

- Parser/reducer recovery gets exactly one fresh bootstrap. A malformed/invalid
  recovery result, or an exhausted bootstrap transport budget, is terminal
  `projection unavailable`; no recovery loop is permitted.
- Bootstrap, stream, and retry share one monotonic generation/single-flight
  controller. Bootstrap aborts the stream and cancels timers; failures while it
  is pending use its bounded budget and cannot open a concurrent stream.
- Static allowlist is derived from the Vite production manifest at runtime;
  malformed manifest, non-regular/outside asset, or emitted source map rejects
  startup. Authenticated unknown assets also reject.
- Refresh must focus the labelled status heading and announce it. Retryable and
  terminal connection states use distinct asserted `aria-live` messages.
- The documents record the intentional divergence from a future separately
  gated Local Web Plan B credential-bootstrap path.

## Deterministic transport closure

- Automatic stream reconnect has exactly four attempts with nominal 250, 500,
  1000, and 2000 ms delays, uniform ±20% jitter, and a 2000 ms cap.
- Each initial/recovery bootstrap has exactly two transport attempts. Exhaustion
  enters terminal `projection unavailable`; the E2E runner itself never retries
  a failed test.
- The store receives delay/clock and random dependencies. Production supplies
  real time/randomness; Playwright installs a test-only fake delay and fixed
  random source before the bundle runs. This makes fourth stream failure,
  bootstrap-budget exhaustion, and the retryable-to-terminal aria-live
  transition deterministic without changing authorization, server behavior, or
  payloads.
- Vite manifest validation is bidirectional: every declared asset exists under
  the build root and every eligible build asset is declared exactly once.

## Injection seam specification

Playwright uses `browserContext.addInitScript` to install an optional override
before any application module executes. It is DevTools-level page injection,
not a served script, route, asset, or manifest entry. The React entry reads and
validates it only when constructing the store; dependencies are never captured
from globals at module load. Without a valid override, production uses real
browser delay/clock/random dependencies; a production-bundle test asserts this
path. The override only resolves local delay promises and returns fixed jitter;
it cannot affect headers, Authorization, URLs, payloads, responses, or server
behavior. Bootstrap retry two uses the first 250 ms policy delay, so it is under
the same fake-delay control.

## Deterministic failure source

Playwright `page.route` is the separate E2E orchestration source for failures.
It matches only already-constructed same-origin bootstrap/SSE requests, asserts
their original URL and Authorization/Origin/Last-Event-ID headers, then aborts
the response/connection for a counted attempt. It neither rewrites request
fields nor fulfills a replacement payload; it is not a served asset and does
not alter runtime-server/production-bundle behavior. The addInitScript override
controls timing only. Together they deterministically prove four stream failures
and two bootstrap failures lead to their specified terminal states.

## Parser/reducer failure source

For parser/reducer negative tests only, a separate Playwright `page.route`
handler first asserts the original request fields then fulfills the browser
request with either a malformed SSE frame or a syntactically valid Event that
violates reducer watermarks. This is the sole response-body synthesis mode; it
is held entirely in browser automation, not in the runtime, static build, Vite
manifest, route inventory, or production fixture. It never changes outgoing
Authorization/Origin/URL. It proves cursor freeze, exactly one fresh bootstrap,
and terminal `projection unavailable` after an invalid recovery bootstrap.
Transport-abort routes never fulfill a body. Route scripts consume a failure
only for the expected path and exact Last-Event-ID; unexpected/parallel matches
fail the E2E assertion and each observation is awaited, binding the count to
the observable single-flight generation without a race.
