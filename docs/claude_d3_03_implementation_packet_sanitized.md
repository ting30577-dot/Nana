# D3-03 implementation exit-review packet (sanitized)

## Scope

Review the D3-03 implementation in relative modules only. No mutation serving
or policy/approval derivation is present.

## Implemented evidence

- `nana_sidecar/read_models.py`: read-only SQLite `BEGIN` snapshot; high-water
  is `MAX(events.id JOIN outbox_events)`; display field whitelists; literal
  stored action states; 2 MiB cap; signed opaque HMAC section tokens carrying
  high-water, aggregate/run watermarks, section, and offset; bounded section
  pages are event projections filtered by `event.id <= token.high_water`, with
  stable ID ordering, and never recompute the high-water. Research, execution,
  artifact, and finding pages are aggregate-type partitions of that stream.
- `nana_sidecar/runtime_app.py`: authenticated `GET /api/v1/bootstrap`; normal
  snapshot or 413 `E_SNAPSHOT_TOO_LARGE` with whitelisted section names and
  page tokens; page requests reject malformed/mismatched tokens.
- `nana_web/src/projection.ts`: pure projection adapter/reducer; canonical
  stable JSON + synchronous SHA-256 fingerprints; exact duplicate idempotence,
  id conflict/decreasing cursor/aggregate and run sequence fail-closed errors;
  unknown events remain activity-only and set degraded; D2 handoff adapter uses
  the same reducer.
- `scripts/test_projection.mjs`: SHA-256 vector, sparse IDs, duplicate,
  conflict, decreasing cursor, aggregate/run sequence, unknown-event degrade,
  and D2 handoff replay checks.
- `tests/test_d3_read_models.py`: privacy, outbox high-water, anchored page
  watermark after later event, event-anchored section pagination across a later
  write, offset bounds, and token tamper rejection.
- `tests/test_d3_runtime_authority.py`: authenticated bootstrap/page route is
  covered by the default-deny matrix.

## Verification

- Python compileall passes.
- Full unittest is the required final evidence (expected suite size is now 300
  with one existing skip after pagination coverage).
- `npm run test:projection` passes.
- `npm run check` passes.

## Codex independent conclusion

PROVISIONAL ACCEPT for D3-03 implementation, contingent on Claude checking:
token integrity and high-water anchoring, whitelist privacy, reducer sequence
semantics, fixture adapter equivalence, and whether aggregate-type event
section pages are an acceptable bounded projection for oversized snapshots. No
authorization inference is intended.
