# D3-03 canonical read-model and sparse-event projection design

Date: 2026-08-01
Status: Codex independent proposal; no implementation yet

## Scope

D3-03 adds one authenticated read-only bootstrap snapshot and a shared pure
TypeScript projection reducer. It consumes D2 facts and D3-02 runtime authority;
it does not add mutation, authorization derivation, Approval decision, export,
or UI rendering.

## Snapshot authority

`GET /api/v1/bootstrap` is an authenticated D3 runtime route, not public. It
opens a SQLite read-only connection and executes `BEGIN` before reading. In the
same read transaction it reads canonical tables/views and computes a high-water
Event ID from `outbox_events JOIN events`; it commits only after all snapshot
rows and aggregate/run watermarks are materialized. The cursor and watermarks
share that high-water boundary. Section pages reuse the opaque high-water token
and those watermarks; they never recompute at current time.

The snapshot contains only canonical facts: Workspace lifecycle; Inquiry,
Resource, Locator, Claim, Evidence, Plan revision; Runs, Actions,
Action states, Receipts, budget and activity states; Artifact/Finding state and
provenance; and an explicit `needs_you` collection derived only from the stored
Action `waiting_approval` state. No Authorization-display or authorization
decision is computed or returned. Paths, data roots, tokens, raw approval
material, and policy-matching inputs are excluded. `effect_unknown`,
`cancelled`, `orphaned`, and pending authorization remain literal values.

## Cursor and event invariants

- Event IDs are globally strictly increasing but non-dense; `10,12,19` is valid.
- SSE receives only events with `id > snapshot.high_water_event_id`.
- Reducer computes `sha256(canonical_json(event))`, where canonical JSON is
  UTF-8, sorted keys, compact separators, and normalized UTC timestamps. Only
  HTTP/SSE receive-time metadata is transport-only; Event/domain timestamps are
  fingerprint fields. An
  exact `(id, fingerprint)` duplicate is ignored; same ID with another
  fingerprint is `E_EVENT_ID_CONFLICT`; any new ID lower than the cursor is
  `E_EVENT_ID_DECREASING`. Integer continuity is never a gap detector.
- Snapshot includes last-seen aggregate versions and run sequences. For each
  incoming event, `aggregate_version == previous + 1` (missing aggregate prior
  version is zero, so first event is one) and, when `run_seq` is
  present, `run_seq == previous_run_seq + 1`; missing or invalid watermarks fail
  closed without cursor advance. The fixture adapter does not sort input: event
  arrays must already be ascending by ID.

## Shared reducer and adapters

`nana_web/src/projection.ts` owns the pure state type, canonical event encoding,
and reducer. Browser SSE and offline D2 replay both call it; no fixture-specific
HTTP shape/client exists. The reducer preserves bounded activity plus explicit
maps for runs, actions, artifacts, findings, receipts, and needs-you state. It
only applies state patches carried by canonical Event type/payload; unknown
events are retained as activity and do not infer success. Artifact changes only
come from `artifact.committed`/`artifact.reconciled` facts.

The offline adapter parses `d2_runtime_handoff_replay.json` into the same typed
initial projection/event sequence. Fixture equivalence is the SHA-256 of
canonical JSON after removing transport-only timestamps and sorting map keys;
the event list is never reordered. A canonical SQLite fixture constructed from
the same handoff facts must produce the same normalized hash. Reducer errors
hold the cursor and require a fresh bootstrap; they never guess a repair.

## Read-model privacy and UI coverage

The endpoint uses a field whitelist: Workspace `id/status/schema_version/
revision`; Inquiry/claim/finding statements and status plus IDs/provenance;
Resource/Locator logical references only as logical (not filesystem) refs and
hash/status metadata; Plan title/revision/status/step titles and approval
required flags but no policy JSON; Run/Action IDs, states, terminal/result enum,
timestamps and capability ID but no args/artifact path; Artifact ID/hash/size/
media type/state/producer ID; Receipt ID/action ID/result/effect-violation as a
boolean and bounded usage counters but no effect paths, undo refs, or raw logs;
Finding statement/status/confidence basis/evidence IDs/producer ID. Provenance
is IDs/relation types only, never embedded refs/effects/policy. Everything else is
excluded by default and tested as absent.

This covers the later minimal UI information architecture: Workspace status;
Inquiry→Plan rail; Run/Action state and Receipt; Artifact/Finding provenance;
activity feed; and literal Needs You (`waiting_approval`) cards. An unknown
event sets `projection_status=degraded` and an upgrade-needed activity banner;
it never changes domain state.

## Runtime boundary

The D3-02 runtime remains the only FastAPI/OpenAPI authority. Bootstrap shares
its session middleware and readiness gate. OpenAPI/TS are regenerated from that
one app. The existing Event SSE route remains the transport.

## Tests and evidence

Snapshot uses `BEGIN`/query-only read snapshot, a bounded 2 MiB response, and a
structured `E_SNAPSHOT_TOO_LARGE` failure. The error lists whitelisted sections;
the client may request a section page with an opaque high-water/offset token.
Every section page is a stable-ID, aggregate-type partition of the Event stream
and filters `event.id <= token.high_water`; it does not page a live aggregate
table. A page that itself exceeds 2 MiB fails explicitly with
`E_SECTION_PAGE_TOO_LARGE` (the client can retry with a smaller limit), never
silently truncating data. Tests cover concurrent later events,
sparse IDs, exact fingerprints, conflicts, decreasing IDs, aggregate/run
sequence violations, canonical fixture hashes, default deny, no mutation
methods, privacy absence, and literal negative states.

## Codex independent decision

- one authenticated bootstrap + shared reducer: ACCEPT
- same-read-transaction high-water: ACCEPT
- sparse IDs and fail-closed sequence validation: ACCEPT
- UI/local re-derivation of authorization or success: VETO
- implementation before Claude convergence: VETO
