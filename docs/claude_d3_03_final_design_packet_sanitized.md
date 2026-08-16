# D3-03 final design convergence packet (sanitized)

## Finding traceability

- F2 Authorization-display → removed; only stored Action `waiting_approval` may
  populate Needs You, never authorization derivation.
- F3 privacy → explicit per-type whitelist and absence tests.
- F5 duplicate → SHA-256 canonical event fingerprint; same-ID conflict errors.
- F6 sequence → snapshot watermarks and exact +1 aggregate/run rules; no reorder.
- F9 fixture → canonical JSON/hash algorithm and six executable negative cases.
- F10 UI → explicit Workspace→Inquiry/Plan→Run/Action/Receipt→Artifact/Finding
  plus Activity/Needs You field map.
- F1/F4/F7 → same-transaction high-water/size, fresh-bootstrap recovery, and
  unknown-event watermark/activity semantics.
- F14 oversize → bounded section/page requests with opaque high-water/offset
  token; pages filter to the same high-water and never silently truncate.
- F15 unknown events → validate sequence watermarks, activity-only patch, and
  degraded status; unknown events cannot alter domain state.

## Decision request

The original first-review response and all finding-to-contract mappings are in
the sanitized archive. Confirm final D3-03 design ACCEPT/VETO/尚未达成共识.
Do not modify files.
