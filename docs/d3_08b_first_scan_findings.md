# D3-08B first scan findings (planning only)

Date: 2026-08-09  
Scope: Approval/export/Receipt UI; no implementation edits.

| ID | Severity | Finding | Evidence / consequence | Decision |
|---|---|---|---|---|
| F08B-01 | P0 | D3-07 joint security gate and D3-08A exit are absent. | Approval UI cannot safely consume a not-yet-frozen capability or command surface. | VETO implementation. |
| F08B-02 | P0 | Canonical Approval lifecycle projection is not exposed to the React store. | UI would have to infer pending/denied/expired/consumed from local state. | VETO until projection contract is accepted. |
| F08B-03 | P0 | No typed approve/deny command is available through the curated journey route. | A browser control could bypass one-time subject binding or call generic D2 schemas. | VETO. |
| F08B-04 | P0 | F07-10 user-selected Workspace-outside target meaning remains unresolved. | Export target UI could normalize an unsafe arbitrary path or violate the authority fixture. | VETO. |
| F08B-05 | P1 | Receipt and `effect_unknown` interaction rules have no browser implementation/evidence. | UI might offer retry, resume, dismiss, or local success. | Open. |
| F08B-06 | P1 | Approval/export accessibility, reload, reconnect, and response-loss evidence is absent. | Authorization-sensitive states are unproven under real browser lifecycle. | Open. |

## Scan conclusion

F08B-01 through F08B-04 are hard blockers. F08B-05 and F08B-06 must be closed
before the 08B exit. No Approval/export UI is authorized.

