# D3-02 authenticated runtime authority design

Date: 2026-08-01
Status: Codex independent proposal; implementation blocked on joint decision

## 1. Scope and non-goals

D3-02 creates one production/runtime FastAPI and one runtime OpenAPI source. It
integrates the accepted D3-01 `WorkspaceRuntime` lifecycle, but exposes only
health, frozen contract metadata, and the existing read-only Event SSE route.

It does not add canonical read models, any mutation method, bootstrap-token
issuance, React UI, Approval handling, export, or a general sandbox claim.

## 2. Authority split

- `nana_sidecar.runtime_app.create_runtime_app` becomes the sole D3 served app.
- It owns exactly one `WorkspaceRuntime`, and derives the Event stream database
  path from that owner rather than accepting a separately configurable path.
- `nana_sidecar.app.create_app` remains a frozen D0 contract artifact for D0
  regression only. It is never mounted, nested, or served by D3.
- Shared schema/catalog construction may be called by both factories, but route
  registration is explicit in the D3 factory; there is no second served route
  authority.
- `nana_web/openapi.json` and `src/generated/api.ts` are generated only from the
  D3 runtime app. The old D0 OpenAPI equality assertion moves to a frozen D0
  fixture/snapshot so it cannot continue claiming the web client authority.

## 3. Lifecycle and readiness

The app has `starting`, `ready`, `draining`, and `failed` states.

1. ASGI lifespan enters `starting`.
2. `WorkspaceRuntime.start()` acquires the OS lock, opens/migrates SQLite, and
   completes real Artifact reconciliation.
3. Only after it returns does the app publish `ready`.
4. Shutdown publishes `draining`, stops accepting query/SSE work, waits for
   tracked request/stream drain, then calls `WorkspaceRuntime.close()`.
5. Any startup failure remains `failed` and the server never reports ready.
6. Any drain/close failure is surfaced and must not cause the process to claim
   a clean shutdown.

The public `GET /healthz` returns only process state and no Workspace path,
identifier, token, version inventory, exception, or reconciliation detail.
`starting`, `draining`, and `failed` return 503; `ready` returns 200.
All other routes return 503 before routing while not ready.

## 4. Exact route policy

Public route inventory:

- `GET /healthz`
- qualifying CORS preflight `OPTIONS` requests (see below)

Authenticated, exact-Origin routes:

- `GET /api/v1/handshake`
- `GET /api/v1/contracts`
- `GET /api/v1/events`
- `GET /openapi.json`

Production docs UI is disabled (`docs_url=None`, `redoc_url=None`). Unknown
paths, trailing-slash redirects, and any future route are authenticated before
routing. No POST/PUT/PATCH/DELETE operation exists in this stage.

Adding any public/bootstrap path requires a new security review and an explicit
allow-list change; prefix matching is forbidden.

## 5. Authentication, Host, Origin, and CORS

- Exactly one ASCII `Authorization: Bearer <session token>` is required on all
  non-public requests and compared in constant time.
- Exactly one `Origin` must byte-match the active `http://127.0.0.1:<port>`
  session origin (decimal port 1-65535); IPv6, HTTPS, localhost, alternate
  spellings, and malformed authorities are rejected.
- Exactly one `Host` must match that origin's authority; ambiguous/malformed
  Host, Origin, Authorization, forwarded-host/proto headers fail closed.
- Security and readiness checks run before router redirects and 404 handling.
- A preflight is public only when it has exactly one matching Origin, exactly
  one requested method from the stage allow-list (`GET`), and a normalized
  requested-header set contained in `{authorization, last-event-id,
  content-type}`. Duplicate or malformed preflight headers fail closed.
- Responses use the exact active Origin, never `*`; allowed methods/headers are
  least privilege; no cookie credential authority is introduced.
- Non-preflight `OPTIONS` is not public.

## 6. SSE and request drain

- Browser delivery remains authenticated `fetch` + `ReadableStream`; native
  `EventSource` is forbidden because it cannot attach Authorization.
- SSE connection admission requires `ready`; a stream admitted before
  `draining` receives cancellation and closes its read-only SQLite connection.
- `Last-Event-ID` duplicate/range checks and sparse-ID semantics remain as D1
  and D3-00 defined. D3-02 does not implement the D3-03 reducer.

## 7. OpenAPI generation

- Export tooling accepts a schema-only construction configuration of the same
  D3 runtime factory; it does not start SQLite or synthesize another app.
- OpenAPI declares bearer authentication and the required Origin header on
  authenticated operations; the public health operation is explicitly
  unauthenticated.
- A route-inventory test compares the runtime router, runtime OpenAPI, checked-in
  OpenAPI snapshot, and generated TypeScript paths/methods.
- A mutation-method scan must remain empty.

## 8. Process evidence

A real loopback runtime-process test must:

1. start the D3 app against a temporary Workspace;
2. observe 503 until the Workspace lifecycle completes, then authenticated
   handshake/Event access and 200 health;
3. prove anonymous, wrong token/origin/host, duplicate headers, unknown paths,
   redirects, and overbroad preflight fail closed;
4. kill the process, wait for confirmed termination, and restart against the
   same Workspace;
5. prove the restarted process owns the Workspace, reconciles, becomes ready,
   and leaks neither the token nor the Workspace path in responses/logs.

This is distinct from the D3-01 child lock-owner test.

## 9. Review gates

Candidate implementation is followed by a no-edit full scan, consolidated D3-02
F# list, batch repair, full re-review, Claude exit review, and evidence summary.
The existing shutdown `ResourceWarning` must be classified against the D3
process/handle/SSE path; it cannot remain unexplained when later mutation
serving is enabled.

## 10. Codex independent decision

- Runtime/OpenAPI authority model: ACCEPT
- Only `/healthz` and qualifying preflight are public: ACCEPT, pending Claude
  security review
- D0 app retained only as a frozen non-served regression artifact: ACCEPT
- Mutation serving in D3-02: VETO
- Implementation before Claude convergence: VETO
