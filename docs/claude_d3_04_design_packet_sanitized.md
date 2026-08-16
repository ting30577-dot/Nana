# D3-04 design packet (sanitized)

## Scope

D3-04 adds only a read-only React Cockpit/Studio to the D3-03 canonical
projection. It does not add a writer, raw Action input, policy/Approval
derivation, export, Tauri, or a second HTTP authority.

## Codex proposal

- The existing D3 runtime remains sole authority. Root and an explicit allowlist
  of build assets are authenticated by the existing exact Host/Origin/Bearer
  gate; no public route, index fallback, source-map route, UI-config route, or
  asset catch-all is proposed.
- Browser E2E uses an in-memory test LocalSession and Playwright extra HTTP
  headers for document/assets/API/SSE. No token appears in URLs, HTML, storage,
  logs, or build files. D3-04 expressly has no human top-level navigation
  path; it is a test-only real-browser mechanism, not a production local-web
  bootstrap.
- React uses one ProjectionStore: canonical bootstrap -> D3 reducer ->
  authenticated `fetch + ReadableStream` SSE. Native EventSource is prohibited.
  Reducer/parser errors freeze cursor and perform one single-flight fresh
  bootstrap; retryable transport failures reconnect with capped jittered backoff
  and the saved cursor; 401/403/session reset is terminal and requires a new
  test-launcher session. There is no integer-gap oracle.
- UI shows only literal stored/reducer facts: Workspace, provenance, Plan,
  Run/Action/Receipt, Artifact/Finding, Activity, and `waiting_approval`.
  `effect_unknown` remains non-dismissible and cannot be retried/resumed.
- A visibly non-canonical local note is permitted but cannot change Plan state.
- Real-browser tests cover headers, sparse/duplicate IDs, reconnect/reload,
  malformed stream recovery, terminal session reset, keyboard, 125%/150% DPI,
  200% text zoom, 320px/400% reflow, reduced motion/contrast, ARIA status,
  fixture exclusion, unauthenticated static rejection, and token/static output
  leakage scan.

## Explicit questions for independent review

1. Is authenticated static serving with test-only Playwright request headers,
   expressly without a human navigation path, an acceptable D3-04 bridge?
2. Are the no-token and no-public-route boundaries sufficiently narrow?
3. Are retryable disconnect, parser/reducer recovery, terminal session-reset,
   and WCAG state/accessibility semantics now complete?
4. Give explicit ACCEPT/VETO/NOT CONSENSUS for D3-04 design and required
   amendments before implementation.
