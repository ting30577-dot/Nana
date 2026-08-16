# Claude D3-02 design review packet (sanitized)

## Frozen inputs

- D3-01 is jointly ACCEPTED: OS Workspace lock before writable SQLite, real D1
  Artifact reconciliation before ready, second instance fail closed, SQLite
  close before lock release, crash/restart covered.
- Existing D1 has a frozen D0 contract app and a separate authenticated runtime
  app with Event SSE. D3 must explicitly converge to one served runtime/OpenAPI
  authority without mounting the D0 app.
- Native EventSource is forbidden; browser SSE uses fetch + ReadableStream.
- No mutation route may be added in D3-02.

## Codex independent proposal

1. The D3 runtime factory is the sole served app and sole web OpenAPI source.
   It owns one WorkspaceRuntime and derives Event storage from that owner.
2. The D0 app remains only a frozen, non-served regression artifact. Its old
   OpenAPI comparison moves to a frozen D0 fixture; the checked-in web OpenAPI
   and generated client come only from D3 runtime.
3. Lifespan states are starting/ready/draining/failed. Workspace lock,
   migrations, and reconciliation precede ready. Query/SSE routes receive 503
   unless ready. Shutdown drains tracked requests/SSE before Workspace close.
4. Exact public inventory is only GET `/healthz` plus qualifying anonymous CORS
   preflight. Health exposes state only: 200 ready, otherwise 503, with no path,
   token, version, exception, or reconciliation detail.
5. Handshake, contracts, events, and OpenAPI require one Bearer token, one exact
   loopback Origin, and one Host matching the Origin authority. Checks precede
   redirects/404. Forwarded host/proto and ambiguous headers fail closed.
6. Public preflight requires exact Origin, GET, and a requested-header subset of
   authorization/last-event-id/content-type. No wildcard Origin, no cookie
   authority, no public non-preflight OPTIONS. Production docs UI is disabled.
7. Runtime router, runtime OpenAPI, checked-in snapshot, and generated TS paths
   are compared. Mutation-method inventory must be empty.
8. Real loopback process evidence covers not-ready→ready, authenticated reads,
   negative security matrix, kill+wait, same-Workspace restart, and response/log
   secret/path non-disclosure.

## Requested review

Independently assess middleware order, readiness semantics, CORS/Host/Origin,
public inventory, schema authority, SSE drain, process evidence, and D0 frozen
regression compatibility. Return ACCEPT/VETO/尚未达成共识 for each material
decision, with F# findings, counterarguments, and convergence conditions. Do not
modify files.
