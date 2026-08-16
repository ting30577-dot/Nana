# D3-06 slice A: boundary and staged authority (sanitized)

Review only this slice; return ACCEPT, VETO, or NOT YET CONSENSUS.

- Scope is exact T2 `python.unittest.locked`; Approval/T3 export and hostile
  sandbox claims are excluded.
- Browser sends a closed typed StartRun/CancelRun union and no test ID,
  executable/shell text, grant/approval decision, authorization material, or
  effect declaration.
- Server fixture owns one frozen built-in test ID, exact args Artifact
  bytes/hash, capability digest, configured PolicyGrant reference, and effect
  ceiling. These are rechecked at execution; replacement/TOCTOU fails closed.
- D3 passes the reference and typed ActionHashMaterial to D2 admission once;
  D2 owns grant matching, consumption, authorization Event/outbox, and durable
  authorization material. D3 never re-queries PolicyGrant/Approval.
- Owner lane validates Project/Inquiry/Plan revision, snapshots plan/budget/
  fixture, and authenticated actor Project scope before creating anything. It
  then idempotently creates one Run, one proposed Action, and a stable command
  log entry. The key is server-bound to actor, target identity, exact revision,
  fixture digest, and an opaque request nonce: same nonce replays, a new nonce
  intentionally reruns. CancelRun targets only a server-issued Run ID and
  rechecks actor scope. D2 admission then authorizes; D2 scheduler claims and
  reserves budget; D2 locked executor enforces allowlist/effect/limits,
  cancellation, Receipt, Artifact, and terminal Events.

  ActionHashMaterial covers capability ID/version/digest, canonical args and
  args_hash, data class, provider, requested effects, network methods, budget,
  risk tier, and reversibility. Actor/target/revision are bound by the
  server-owned Run/Action relation and envelope. Scheduler claim, cancel, and
  recovery CAS the same Action lifecycle state; first transition wins and
  later transitions are durable no-ops.

Admission grant consumption and scheduler budget reservation are separate
D2-owned transactions. Recovery gives an authorized-but-unclaimed Action one
terminal budget_exceeded/cancelled/orphaned fact and never re-admits or
reclaims it; consumed grant is an intentional admission fact, not an implicit
refund.

Question: is this boundary and staged delegation safe and sufficient? Name a
concrete counterexample if not.
