# D3-08A / D3-08B / D3-09 planning first scan

Date: 2026-08-09  
Scope: decomposition and entry planning only; no implementation authorization.

| ID | Severity | Finding | Evidence / consequence | Decision |
|---|---|---|---|---|
| F08-01 | P0 | D3-08A has no joint entry decision tied to a D3-07 exit. | Browser mutations before the export/approval security boundary would create an unreviewed public surface. | VETO implementation. |
| F08-02 | P0 | No typed browser mutation transport contract is frozen for command response versus projection truth. | UI could treat a 2xx response as durable success or bypass structured errors. | VETO until contract and tests are ACCEPTed. |
| F08-03 | P1 | Create/edit/start/cancel form eligibility and duplicate-submit behavior are unspecified in code. | A user could send stale revisions or start/cancel an impossible state. | Open; resolve before 08A implementation. |
| F08-04 | P1 | Browser negative-state/accessibility/DPI coverage is only planned. | Keyboard users and session/stream failures could see misleading controls. | Open. |
| F08-05 | P0 | D3-08B Approval lifecycle facts and one-time decision command are not yet exposed by the runtime. | UI cannot safely decide, consume, or replay an Approval. | VETO implementation. |
| F08-06 | P0 | F07-10 target-directory conflict is inherited by export UI. | A target chooser cannot be implemented until authority and security gate agree on “user-selected Workspace-outside”. | VETO. |
| F08-07 | P1 | Receipt/effect_unknown presentation rules are not yet backed by browser tests. | UI might offer retry/resume/dismiss or rewrite uncertainty as success. | Open. |
| F09-01 | P0 | D3-09 release evidence cannot pass while D3-06 Claude exit and D3-07 joint gate are unresolved. | Final journey claims would be based on incomplete joint review. | VETO release. |
| F09-02 | P1 | Ten-run clean fixture and fault matrix do not yet exist. | Narrow tests cannot prove the full dev journey or crash/reconnect semantics. | Open. |
| F09-03 | P1 | Authority evidence-index synchronization is not yet specified as a release artifact. | Repeats the prior code-green/evidence-missing handoff failure. | Open. |

## Scan conclusion

F08-01, F08-02, F08-05, F08-06, and F09-01 are hard blockers. F08-03,
F08-04, F08-07, F09-02, and F09-03 must be resolved before their respective
stage exits. No D3-08A, D3-08B, or D3-09 implementation is authorized by this
planning scan.

