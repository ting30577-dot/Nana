# D3-03 joint design decision record

Date: 2026-08-01
Status: implementation exit review complete

| Finding | Decision | Resolution |
|---|---|---|
| F2 Authorization-display source | ACCEPT | Remove Authorization-display entirely. Bootstrap exposes stored Action state only; `needs_you` is only `waiting_approval`, not a PolicyGrant/Approval decision or re-derived authorization. |
| F3 privacy scope | ACCEPT | Replace blacklist with explicit per-type field whitelist; paths, raw args, policy JSON, effect paths, undo refs, logs, tokens, and raw approval material are absent-by-test. |
| F5 duplicate semantics | ACCEPT | Fingerprint is SHA-256 of canonical UTF-8 JSON (sorted keys, compact separators, normalized UTC timestamps). Same ID+fingerprint ignores; same ID+different fingerprint returns `E_EVENT_ID_CONFLICT`. |
| F6 sequence semantics | ACCEPT | Snapshot carries aggregate-version and run-sequence watermarks. Every new event must increment its aggregate version and present run sequence by one; violation returns structured error with no cursor advance. Input is not reordered. |
| F9 fixture equivalence | ACCEPT | Canonical normalized JSON/hash is defined; event order must already be ascending. SQLite and D2 replay fixtures compare the same normalized projection hash, including negative/order cases. |
| F10 UI sufficiency | ACCEPT | Explicit later UI information architecture is Workspace → Inquiry/Plan → Run/Action/Receipt → Artifact/Finding plus Activity and literal Needs You. |
| F1 transaction/size | ACCEPT | `BEGIN` query-only snapshot, high-water read in the same transaction, 2 MiB bounded payload, `E_SNAPSHOT_TOO_LARGE`, no lock/mutation path. |
| F4 reducer recovery | ACCEPT | Fail-closed reducer holds cursor and asks for fresh bootstrap; no local repair or inferred success. |
| F7 unknown events | ACCEPT | Preserve unknown event as activity, set degraded projection status, show upgrade-needed banner, never patch domain state. |
| F13 finding-to-contract traceability | ACCEPT | The first-review findings are archived verbatim in the sanitized response and mapped one-to-one to this table; transaction/recovery/unknown-event are explicit independent items. |
| F14 snapshot oversize | ACCEPT | `E_SNAPSHOT_TOO_LARGE` includes section list and a bounded section/page contract: client requests one whitelisted section with an opaque high-water/offset token; every page filters `event.id <= token.high_water`, and no page silently truncates. |
| F15 unknown-event sequencing | ACCEPT | Unknown events still consume and validate aggregate/run watermarks; they are retained only in activity with degraded status and cannot patch domain state. Invalid watermark fails closed. |
| F16 pagination/watermark anchor | ACCEPT | Snapshot rows, watermarks, and high-water share one `BEGIN` snapshot; section pages reuse that token and never recompute current-time watermarks. |
| F17 whitelist substructures/time | ACCEPT | Provenance is IDs/relation types only; effect violation is boolean; only receive time is transport metadata. |
| F18 new aggregate | ACCEPT | Missing aggregate prior version is zero, so first Event must be aggregate version one; positive and negative tests are required. |

Codex: ACCEPT after these resolutions. Claude's first review had three VETO and
two not-consensus findings; a final Claude design review is required before
implementation.

## Final design decision

- F2, F3, F5, F6, F9, F10, F13, F14, F15: CLOSED at design level
- Codex: ACCEPT
- Claude: ACCEPT
- D3-03 implementation: authorized to begin, but not yet complete

The concurrent-write pagination-equivalence case is a required implementation
test, not merely a design assertion. No mutation serving is authorized.

## Implementation exit decision

- Codex: ACCEPT. The read-only bootstrap and signed recovery pages retain the
  D2/D3-02 authority boundary; no mutation, authorization derivation, or
  policy/approval read was introduced.
- Claude: ACCEPT (with recorded clarification). The final review accepted the
  implemented high-water paging, token section binding, and explicit oversize
  failure after the full suite passed.
- Decision: ACCEPT. D3-04 may begin.

Evidence: `compileall` passed; full Python suite ran 303 tests with one existing
skip and no failures; projection self-test and TypeScript check passed. The
earlier expected count of 300 preceded three closure tests: same-token/same-
offset idempotence after a later write, cross-section token rejection, and
section-page over-ceiling failure. Recovery tokens are tied to the in-memory
LocalSession secret and deliberately fail closed after restart; the browser must
bootstrap again.

## Finding-to-contract map

F2→Authorization source, F3→privacy whitelist, F5→fingerprint, F6→sequence
watermarks, F9→canonical fixture hash/negative tests, F10→UI coverage. Snapshot
transaction/size is F1, reducer recovery F4, unknown event F7, and oversize/
unknown sequencing are F14/F15. No finding is silently merged or dropped.
