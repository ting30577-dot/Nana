# D3-08A stage decomposition draft — core mutation UI and negative-state usability

Status: planning only; no implementation authorization.

## Boundary

D3-08A adds the smallest browser mutation surface for the typed D3-06 journey
commands (create/edit/propose, start, and cancel) after D3-07 exits. It does not
add Approval/export controls, a new runtime, a second API client, or any local
canonical state. Every visible result must be reconciled from the authenticated
command response plus the canonical bootstrap/SSE projection.

## Sub-stages

| Sub-stage | Deliverable | Hard guard |
|---|---|---|
| 08A-00 | Entry decision record and frozen command-to-form map | D3-07 joint exit required; no route or UI write before ACCEPT |
| 08A-01 | Typed browser command transport using `fetch` and bearer header | one sole runtime route; structured errors rendered without guessing |
| 08A-02 | Create/edit/propose controls for the existing typed contracts | server-owned IDs/revisions; no arbitrary Action/Grant payload |
| 08A-03 | Start/cancel controls with state guards | only canonical eligible states enable controls; duplicate submit is idempotent |
| 08A-04 | Reconciliation after command response, reload, and SSE | response is not success proof; UI returns to projection truth |
| 08A-05 | Browser E2E, keyboard, DPI, and negative-state evidence | verify denied/conflict/session-expired/stream-loss paths and no optimistic success |

## Required invariants

- Authorization header is attached by `fetch`; no `EventSource` and no unauthenticated mutation.
- Local form text is draft-only until a typed command is accepted; local state never becomes canonical.
- A 2xx command result is displayed as an accepted request, then reconciled from projection.
- 409/422/500 structured errors preserve code and field context without inventing a state.
- Start/cancel controls are disabled for impossible or terminal states and remain safe under double click.
- Reload and sparse/reordered SSE produce the same projection as offline replay.
- Workspace lock/readiness and D2 admission/scheduler/executor remain server-side gates.

## Exit evidence

Focused TypeScript tests, full `npm run check`, real-browser Playwright tests,
accessibility/DPI screenshots or assertions, mutation route audit, and a second
no-edit scan with every F08A finding closed or explicitly accepted.

