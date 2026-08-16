# D3-02 design resolution packet (sanitized)

## Resolved boundaries

- `redirect_slashes=False`; middleware checks auth before router redirects or
  404. Public pre-auth set is exact `/healthz` plus valid CORS preflight.
- Failed startup is terminal: D3-01 cleanup runs, then lifespan re-raises and
  the process exits. Successful cleanup releases the lock; failed SQLite close
  retains the lock and is reported as fail-closed. A persistent failed server is
  not advertised.
- Origin authority is an explicitly configured numeric loopback IP with a
  required port and no credentials/path/query/fragment. D3-02 fixes the value
  to `http://127.0.0.1:<port>` with port 1-65535; IPv6, HTTPS, `localhost`, and
  alternate spellings fail closed. Exact string and exact Host authority
  matching are required.
- SSE streams are tracked. Drain stops new admissions, signals termination,
  waits a bounded deadline, cancels remaining tasks, awaits generator cleanup,
  and only then calls WorkspaceRuntime.close().
- D3 OpenAPI must be a superset of the frozen D0 path/method and component
  contract surface; the checked-in web snapshot and generated TS derive only
  from D3 runtime.
- Every route gets an independent negative auth/Origin/Host matrix; OpenAPI is
  not accepted as proof of middleware enforcement.
- Preflight allows only `authorization` and `last-event-id` requested headers.
  A route/method guard fails if any POST/PUT/PATCH/DELETE appears. Any future
  mutation stage must expand the preflight contract and negative matrix in the
  same reviewed change.

## Required evidence before implementation exit

1. route inventory and `redirect_slashes=False` scan;
2. startup failed/lock release and cleanup-failure process tests;
3. exact Origin/Host and duplicate/forwarded header matrix;
4. bounded graceful SSE drain order plus forced-timeout path;
5. D0 fixture compatibility and one runtime OpenAPI generation source;
6. real runtime-process crash/restart and no mutation-method scan.

The former design-review ambiguities B3 and B7 are now explicit contract
decisions, not implementation choices.

Return ACCEPT/VETO/尚未达成共识 for the resolved D3-02 design. Do not modify
files.
