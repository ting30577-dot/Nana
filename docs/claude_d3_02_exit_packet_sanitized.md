# D3-02 exit review packet (sanitized)

## Scope

D3-02 provides the sole served, authenticated, read-only runtime/OpenAPI
authority. No mutation method, Approval flow, external export, React UI, or
general sandbox capability is enabled.

## Implemented decisions

- Factory takes one D3-01 WorkspaceRuntime and derives SQLite Event streaming
  from its canonical database path; no public event-stream override remains.
- Lifespan start completes D3-01 lock/migration/reconciliation before ready.
  Failed start re-raises after D3-01 cleanup; failed cleanup remains fail-closed.
- Exact public inventory: GET `/healthz` plus valid CORS preflight only.
  Docs/redoc are disabled and slash redirects are disabled.
- Every other route requires one Bearer session, exact mandatory
  `http://127.0.0.1:<decimal port>` Origin, and exact matching Host. Missing
  Origin, localhost/IPv6/HTTPS/aliases, duplicates, and forwarded headers fail
  closed.
- Preflight permits only GET and requested headers authorization/last-event-id.
  A mutation inventory guard and an injected-route meta-test reject any
  POST/PUT/PATCH/DELETE.
- SSE stop signal and bounded timeout ensure stream cleanup before Workspace
  close; timeout path cancels the stream before SQLite/OS lock release.
- Runtime OpenAPI is the checked-in web/TypeScript source. A frozen D0 OpenAPI
  fixture is checked as compatible path/schema subset.

## Findings closure

- F1 frozen D0 snapshot/live runtime collision: CLOSED.
- F2 configurable stream identity bypass: CLOSED.
- F3 legacy public runtime tests/lifecycle gap: CLOSED.
- F4 D0/D2 evidence-manifest drift: CLOSED; both 102-entry manifests validate.
- F5 inherited PySide6 shutdown diagnostic: recorded as non-blocking only until
  the later real-mutation precondition; focused D3 runtime strict tests are
  clean.

## Verification

- focused D1+D3 HTTP/runtime suites: 24 passed
- full strict-warning Python: 293 passed, 1 existing environment skip, 0 fail
- Python compileall: pass
- TypeScript check: pass
- D0/D2 manifests: 102 entries each, 0 mismatches, digest
  `d7254aa074b503b5a404d1bdaaa16478e6fc87c9d88393fa0f9f00380285d02b`
- D3-02 scoped manifest digest:
  `72acdfb9c18a6dca3108064dfc255f77f2803bfb0ebba6e24404ad8f1cbce6cc`

## Requested decision

Review implementation behavior, security boundaries, evidence claims, and
remaining blockers. Return explicit D3-02 ACCEPT, VETO, or 尚未达成共识; list
any new F# finding. Do not modify files.
