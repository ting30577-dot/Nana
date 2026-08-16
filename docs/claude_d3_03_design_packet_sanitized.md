# Claude D3-03 design review packet (sanitized)

## Fixed inputs

- D3-01 Workspace lifecycle and D3-02 sole runtime/OpenAPI authority are
  ACCEPTED and read-only.
- D2 facts are Actions, Events, outbox_events, ActionAuthorizations, Artifacts,
  Runs, Receipts, and the locked-unittest handoff replay fixture.
- Browser SSE remains authenticated fetch + ReadableStream, never EventSource.
- D3 must not re-derive PolicyGrant/Approval authorization or invent success.

## Codex proposal

1. Add authenticated GET `/api/v1/bootstrap` to the sole D3 runtime. One
   read-only SQLite transaction reads canonical rows and an outbox Event
   high-water ID; SSE continues at ID greater than the cursor.
2. Snapshot includes stored Workspace/research/Plan/Run/Action/
   Authorization-display/Receipt/Artifact/Finding/Needs-You facts, excluding
   paths, tokens, raw approval material, and policy-matching inputs.
3. One pure typed TypeScript reducer handles browser SSE and offline fixture.
   IDs are strict but sparse; exact duplicate ignored; mismatch/decreasing ID or
   aggregate/run sequence violation fail closed with no cursor advance.
4. Unknown Event stays activity only; terminal/negative states are literal.
   Artifact state changes only from canonical Artifact events.
5. D2 replay fixture and a canonical SQLite fixture normalize identically.

## Requested review

Independently assess snapshot consistency, event/reducer rules, authorization
and privacy leakage, D2 fixture equivalence, default-deny impact, and whether
the read model is sufficient for the later minimal UI. Return
ACCEPT/VETO/尚未达成共识 with F# findings, counterarguments, and convergence
conditions. Do not modify files.
