# D3-02 final design convergence packet (sanitized)

The two remaining design ambiguities are closed:

- B3/F5: only `http://127.0.0.1:<port>` (decimal 1-65535) is accepted; exact
  Origin and Host authority matching is required. IPv6, HTTPS, localhost,
  alternate spellings, missing port, credentials, and path/query/fragment are
  rejected.
- B7/F9: only `authorization` and `last-event-id` are permitted in a D3-02
  preflight. A route scan fails if any mutation method appears. Future mutation
  work must expand the preflight allow-list and matrix in the same reviewed
  change.

All other Claude findings are resolved in the accompanying decision record:
redirects disabled, startup failure exits after D3-01 cleanup, bounded SSE
drain precedes Workspace close, D0 fixture compatibility is explicit, and
middleware auth has an independent negative matrix.

Return final D3-02 design decision: ACCEPT, VETO, or 尚未达成共识. Do not
modify files. Implementation has not started.
