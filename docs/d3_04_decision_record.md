# D3-04 design and exit decision record

Date: 2026-08-08
Status: implementation exit ACCEPT; D3-05 design authorized

## Joint result

- Codex: ACCEPT after candidate freeze, full no-edit scan, F1-F8 batch repair,
  final re-review, executable verification, and visual QA.
- Claude: ACCEPT on the supplied sanitized evidence, with the explicit limit
  that Claude did not independently read raw source/logs or rerun the suite.
- Joint decision: D3-04 ACCEPT. D3-05 design only may begin. No D3-05
  implementation is authorized until its own joint design decision.
- No mutation serving, Local Web Plan B, authorization derivation, Approval
  handling, export, or Tauri work is authorized by this decision.

## Frozen implementation checks

1. React consumes only D3-03 bootstrap plus the shared reducer.
2. SSE uses authenticated `fetch + ReadableStream`, never `EventSource`.
3. Static UI is authenticated and manifest-allowlisted; no public, fallback,
   source-map, or config route is added.
4. Browser timing, transport-abort, and malformed-response test modes are
   mutually exclusive and remain outside production artifacts.
5. Retry, fresh-bootstrap, session-expired terminal states, and accessibility
   announcements are deterministic and distinguishable.
6. The stage followed candidate implementation -> no-edit full scan ->
   consolidated F# findings -> batch repair -> final re-review -> evidence ->
   Claude exit review.

## Exit disposition

- F1-F8: ACCEPT by Codex and Claude.
- New P0/P1 blockers: none identified.
- Overall D3-04: ACCEPT.
- D3-05 authorization: ACCEPT for design only.

## Explicitly unresolved, non-blocking

1. **Not yet consensus:** whether F6 should additionally require a
   clean-environment direct replay record. This is recommended evidence
   strengthening, not a D3-04 exit blocker.
2. **Not yet consensus:** whether the project's strongest dual-source bar
   requires another independent code-level audit of F1/F2, because Claude's
   exit review used the sanitized evidence packet rather than raw source/logs.
   This does not authorize implementation and does not block D3-05 design.

The normalized Claude response is retained in
`docs/claude_d3_04_exit_response_sanitized.md`.
