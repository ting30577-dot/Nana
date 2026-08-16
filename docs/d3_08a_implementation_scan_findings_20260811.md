# D3-08A implementation and no-edit scan

Date: 2026-08-11  
Status: all findings closed

The earlier `d3_08a_first_scan_findings.md` remains the historical planning
scan. D3-07 is now accepted under the Codex-only governance decision, so its
predecessor veto no longer describes the current gate.

| ID | Severity | Finding | Repair / evidence | State |
|---|---|---|---|---|
| F08A-01 | P0 | Historical D3-07 predecessor veto. | D3-07 Codex-only implementation exit and exact machine gate are ACCEPT. | closed |
| F08A-02 | P0 | Typed browser transport was absent. | One handshake-derived, default-deny `fetch` transport posts only generated Journey commands. | closed |
| F08A-03 | P1 | Draft/canonical boundary was absent. | Local form state is labelled draft; every accepted command bootstraps canonical facts before reconciliation. | closed |
| F08A-04 | P1 | Start/cancel and duplicate-submit guards were absent. | Canonical eligibility plus one global single-flight; browser test proves a double click emits one command. | closed |
| F08A-05 | P1 | Conflict and transport uncertainty were not usable. | 409 refreshes canonical state; response loss becomes `outcome_unknown` and exact-ID replay only. | closed |
| F08A-06 | P1 | Browser accessibility/reflow evidence was absent. | Chromium success/cancel, 320px reflow and Axe serious/critical assertions pass. | closed |
| F08A-07 | P1 | Generic contracts could leak unsupported controls. | Component command map is explicit and contains no Approval/export/Grant/Publish control. | closed |
| F08A-08 | P0 | Bootstrap omitted canonical Projects, blocking the real journey after a committed CreateProject. | Added field-whitelisted `projects` read model, frontend collection and Python/TS tests. | closed |
| F08A-09 | P2 | A broad status text collided with legacy E2E locators. | Status live region uses precise command text; all 17 historical browser tests pass. | closed |
| F08A-10 | P0 | A committed command with a lost/malformed response could be resent under a new identity. | Store freezes the command object, refreshes canonical state and offers only exact command-ID replay. | closed |
| F08A-11 | P1 | Server error messages/details could expose non-public context. | UI renders message/details only when `data_safe=true`; dedicated test proves withholding. | closed |
| F08A-12 | P0 | A known-new event could degrade the projection while mutation controls remained enabled. | All mutation controls require `projection_status=ready`. | closed |
| F08A-13 | P1 | Frontend known-event table diverged from backend for Relation and budget events. | Added exact `relation.created`, `budget.updated` and `budget.threshold_reached` parity with projection tests; real journey stays ready. | closed |

## Final read-only scan

- Production source contains no `EventSource`.
- `JourneyWorkbench.tsx` contains no Request/Decide/Consume Approval,
  AuthorizeAction, PublishExport or export control.
- Browser StartRun contains only IDs/revisions/random seed; server retains the
  fixed backend, capability, test ID and limits.
- The browser never supplies authorization, path, filename, raw bytes or
  external effects.
- A command result is never used as filesystem or execution success proof.
- Degraded projection, missing handshake capability, session expiration and
  concurrent submission all fail closed.

Conclusion: **ACCEPT** for D3-08A's exact core mutation UI boundary.
