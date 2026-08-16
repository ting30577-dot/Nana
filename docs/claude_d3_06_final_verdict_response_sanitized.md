# Claude D3-06 final design verdict response (sanitized)

Date: 2026-08-08.

## Decision

**ACCEPT.** Claude accepts the narrow exact-T2 D3-06 design for
implementation.

## Accepted basis

- One Workspace owner-lane recovery coordinator is the only terminal writer.
- Claim/spawn/cancel/recovery use one Action-state CAS fence; watchdog and
  worker are input/report sources, not SQLite terminal writers.
- Receipt/Artifact/Event and the unique Action-causation budget settlement are
  one owner-lane transaction; late paths read the terminal/usage row and
  no-op.
- `unknown_pending` classification is deterministic: confirmed residual or
  failure to confirm death by deadline is `orphaned`; confirmed death with
  unverifiable effects is `effect_unknown`. Both are consumed-budget
  decrement settlements and remain distinct in audit/projection vocabulary.
- Worker receives no DB handle; Gate-G confirms process/job/descendant death
  and cleanup; Gate-H records auditable gate decisions.
- Conservative billing with no automatic refund is an explicit D3-06 product
  policy and is visible in the Receipt.

## Implementation conditions

Claude's remaining observations are implementation checks, not design blockers:
the real owner-lane transaction must be atomic, Gate-G reaping must preserve
the distinction between `effect_unknown` and `orphaned`, and Receipt copy must
explain conservative billing. D3-06 implementation is authorized; D3-07 is
not included.
