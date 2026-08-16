# Nana D3 full-plan decision record

Date: 2026-08-01

## Joint result

Codex: **ACCEPT**.

Claude: **ACCEPT at design level**, with evidence assertions assigned to the
stages where their code exists.

Frozen order:

`D3-00 → D3-01 → D3-02 → D3-03 → D3-04 → D3-05 → D3-06 → D3-07 →
D3-08A → D3-08B → D3-09`

## Stage decisions

| Stage | Joint design state |
|---|---|
| D3-00 complete decomposition and frozen contracts | ACCEPT |
| D3-01 Workspace lifecycle | ACCEPT to begin formal review |
| D3-02 authenticated runtime authority/readiness | ACCEPT |
| D3-03 read models/snapshot/reducer | ACCEPT |
| D3-04 read-only React/browser SSE | ACCEPT |
| D3-05 canonical journey writers | ACCEPT |
| D3-06 locked-test orchestration | ACCEPT |
| D3-07 Approval/controlled export | ACCEPT as a decision gate; export remains disabled until joint gate ACCEPT |
| D3-08A core mutation UI | ACCEPT |
| D3-08B authorization-sensitive UI | ACCEPT |
| D3-09 final ten-run/evidence gate | ACCEPT |

## Evidence assertions

- D3-01 must prove OS lock authority only, no persisted ownership row/marker,
  no schema migration, and real D1 reconciler behavior after process death.
- D3-06 must prove its exact frozen T2 execution path cannot create, decide,
  authorize from, or consume one-time Approval; it uses only the frozen
  PolicyGrant path.
- D3-07 is the first D3 stage that implements and proves the combined R1
  one-time Approval transaction.

Claude correctly distinguished design closure from future code evidence. These
assertions are not claimed as already tested; each stage remains incomplete
until its assigned evidence exists.

## Review protocol

Every stage uses: candidate implementation → complete no-edit scan → consolidated
findings → batch repairs → complete final re-review → evidence closure → Claude
exit review. No implementation test alone closes a stage.

## Current planning-mode amendment (2026-08-10)

For the current continuation, the product owner explicitly authorized a
GPT-only revision of the D3 plan and instructed Codex not to call, retry, or
await Claude. Codex **ACCEPTS** this as a plan-maintenance decision only:

- the live D3-07 gate remains unresolved and all implementation/filesystem
  write flags remain false;
- historical Claude packets and transport records remain evidence, not a new
  independent verdict;
- GPT may perform the plan-only scan, consistency repairs, and evidence/diff
  checks;
- this amendment does not authorize Approval/T3 implementation, capability
  registration, mutation serving, or external filesystem writes.

Any later stage implementation still requires its own explicit entry decision;
the plan cannot self-authorize a gate transition.
