# D3-03 design resolution packet (sanitized)

The first review findings are closed by these explicit contracts:

- No Authorization-display field is returned. `needs_you` is only a read-only
  view of stored Action state `waiting_approval`; no PolicyGrant/Approval
  authorization is queried or inferred.
- Bootstrap uses a per-type field whitelist. No paths, raw args/policy JSON,
  effect paths, undo refs, logs, tokens, or raw approval material can appear.
- Event fingerprint is SHA-256 of canonical UTF-8 JSON (sorted keys, compact
  separators, normalized UTC timestamp strings). Same ID+fingerprint ignores;
  same ID with another fingerprint errors; decreasing new IDs error.
- Snapshot includes aggregate-version/run-sequence watermarks. Incoming events
  must increment each applicable sequence exactly by one; no sort/reorder is
  performed; errors do not advance the cursor.
- Fixture equivalence is an executable normalized canonical JSON hash, with
  already-ascending event input and explicit out-of-order negative tests.
- Later UI coverage is explicitly mapped to Workspace, Inquiry/Plan,
  Run/Action/Receipt, Artifact/Finding, Activity, and literal Needs You.
- Read transaction is `BEGIN` query-only, high-water in same transaction, with a
  2 MiB response cap and structured oversize error. Reducer failure requires a
  fresh bootstrap. Unknown events degrade activity only.

Return final D3-03 design ACCEPT/VETO/尚未达成共识. Do not modify files.
