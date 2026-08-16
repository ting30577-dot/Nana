# Claude D3-02 design response (sanitized)

Claude accepted the direction but returned `尚未达成共识` for four boundary
decisions and no VETO:

- F3: explicitly disable slash redirects and prove auth precedes redirect/404.
- F4: define failed startup as lock-releasing process exit (or justify a
 持锁 resident failed mode) and test it.
- F5: freeze a single numeric loopback Origin form, including scheme/host/port,
  and test alternate spellings.
- F6: make SSE graceful drain bounded and prove stream termination precedes
  SQLite close and lock release.
- F7: add graceful SSE drain and failed-state/second-instance evidence.
- F8: compare D3 OpenAPI against a frozen D0 fixture for compatible path/schema
  coverage.
- F2 challenge: add an independent middleware-auth enforcement matrix; OpenAPI
  shape alone cannot prove middleware security.
- F9: remove unused `content-type` from the preflight allow-list.

Claude accepted the narrow public route inventory, one runtime/OpenAPI
authority, CORS fail-closed posture, no mutation routes, and the fetch+
ReadableStream SSE boundary.
