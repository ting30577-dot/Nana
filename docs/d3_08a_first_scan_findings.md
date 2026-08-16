# D3-08A first scan findings (planning only)

Date: 2026-08-09  
Scope: core mutation UI and negative-state usability; no implementation edits.

| ID | Severity | Finding | Evidence / consequence | Decision |
|---|---|---|---|---|
| F08A-01 | P0 | D3-07 joint exit is absent. | Mutation UI could be built against a command/projection boundary that later changes under the T3 gate. | VETO implementation. |
| F08A-02 | P0 | No typed browser mutation transport is frozen. | A component could post raw command/domain objects or treat 2xx as canonical success. | VETO until transport/reconciliation contract is accepted. |
| F08A-03 | P1 | Create/edit/propose form state and dirty-draft rules are not implemented. | Browser local text could be mistaken for canonical Inquiry/Plan/Finding state. | Open. |
| F08A-04 | P1 | Start/cancel eligibility and double-submit behavior are not implemented. | Stale revisions or impossible state transitions could reach the runtime. | Open. |
| F08A-05 | P1 | Structured validation/conflict/session errors lack mutation UI presentation. | Users could not distinguish rejected, pending, and canonical states. | Open. |
| F08A-06 | P1 | Real-browser keyboard, DPI, reload, reconnect, and negative-state evidence is absent. | Accessibility and recovery requirements are unproven. | Open. |
| F08A-07 | P1 | Generic D2 command schemas coexist with the curated Journey route. | A future client change could accidentally render unsupported Approval/Grant controls. | Open; retain exact route mapping and add UI allow-list tests. |

## Scan conclusion

F08A-01 and F08A-02 are hard blockers; F08A-03 through F08A-07 must be closed
before the 08A exit. This is a planning scan only; no component or mutation
route is authorized.

