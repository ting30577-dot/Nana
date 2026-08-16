# D3-08B stage decomposition draft — Approval, export, and Receipt UI

Status: planning only; no implementation authorization.

## Boundary

D3-08B consumes canonical Approval, Action, Artifact, export, and Receipt facts
from the sole runtime. It may expose a typed decision control only after D3-07
registers and proves the exact capability. It must not infer authorization,
write files, call PolicyGrant, or claim export success from browser state.

## Sub-stages

| Sub-stage | Deliverable | Hard guard |
|---|---|---|
| 08B-00 | Joint entry record and UI fact/state matrix | D3-07 and D3-08A exits required |
| 08B-01 | Projection support for Approval lifecycle and export-linked Receipt | sparse IDs, replay equivalence, no synthetic facts |
| 08B-02 | Typed Approval decision UI | decision is bound to exact Action/ActionHash and consumed once |
| 08B-03 | Safe export-target interaction | must reconcile F07-10 with authority; no arbitrary path or route before ACCEPT |
| 08B-04 | Receipt/effect-unknown presentation and quarantine | unknown is terminal for UI; no retry/resume/dismiss/success mutation |
| 08B-05 | Browser E2E and accessibility evidence | pending/denied/expired/consumed/unknown plus reload/reconnect |

## Required invariants

- `waiting_approval`, denied, expired, consumed, and `effect_unknown` are rendered from canonical facts only.
- Approval decision cannot be replaced by a PolicyGrant or browser-selected capability.
- Export UI never writes directly and never treats a command response as durable side-effect proof.
- Before write begins, the runtime must have exact target/capability admission; after uncertainty, the Receipt remains `effect_unknown`.
- Any user-selected Workspace-outside directory requirement must be resolved with the authoritative T3 fixture and joint review before implementation.

## Exit evidence

Projection and command tests, complete canonical-state matrix, real-browser
approval/receipt tests, no-optimistic-success assertions, security review of the
target chooser, and evidence-index synchronization.

