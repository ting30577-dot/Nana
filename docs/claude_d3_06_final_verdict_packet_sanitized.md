# D3-06 final design verdict packet (sanitized)

Return exactly one verdict for D3-06: ACCEPT, VETO, or NOT YET CONSENSUS,
followed by one short reason. No code or test claims.

Scope is only exact T2 `python.unittest.locked`; browser has typed StartRun /
CancelRun and no test/shell/authorization/effect inputs. Server fixture owns
frozen test ID, args bytes/hash, capability digest, PolicyGrant reference, and
effect ceiling. The worker receives the same immutable verified snapshot bytes.
D2 `ActionHashMaterial` covers capability ID/version/digest, canonical args /
args_hash, data class, provider, requested effects, network methods, budget,
risk tier, and reversibility. Actor/target/revision are server-bound Run/
Action relations and command envelope; owner lane checks actor scope.

Admission, scheduler, and locked executor remain D2 authorities. Grant
consumption and budget reservation are separate but recovery gives an
authorized-unclaimed Action one terminal fact; no re-admit/reclaim or implicit
refund. Claim, cancel, and recovery CAS the same lifecycle state. Replay while
non-terminal returns durable state without blocking. Claim/spawn has a CAS
fence: pre-spawn cancel releases; after spawn fence, cancel is
termination-aware. Timeout is a distinct terminal state; uncertain effects
commit-settle usage exactly once (unique Action causation ID; terminal CAS and
ledger decrement are one owner-lane transaction, never refund).

Execution is phased: owner-lane preflight/claim, worker-only extraction of D2's
frozen process segment with no DB handle, owner-lane completion. A watchdog
owns timeout. Worker crash becomes effect_unknown and then commit-settles its
reservation exactly once in that owner-lane transaction; orphaned means confirmed residual process/termination
failure and also commit-settles once. The watchdog only signals and never settles. Gate-G confirms
death/escalation/reaping. Gate-H records tamper-evident gate decision Events.
Receipt/Artifact appear only after owner-lane commit.

State proof: proposed -> authorized -> claimed -> spawn_committed/running ->
terminal, with claim/spawn/cancel/recovery conditional writes on one Action
state. Cancel before spawn fence is cancelled + one release; after the fence,
worker result determines cancelled/effect_unknown/orphaned. Crash after fence
is effect_unknown with one eventual owner-lane commit settlement. Replay of any non-terminal command
returns its durable state without new work. D2 ledger asserts one reservation
increment and one completion decrement by unique Action causation ID in the
same terminal CAS transaction; uncertain effects are charged as consumed
(decrement, never freeze or refund). A single owner-lane recovery coordinator
is the only terminal writer: worker reports, watchdog timeout/cancel intents,
and Gate-G liveness are inputs. It classifies non-terminal `unknown_pending`
deterministically: confirmed residual or failure to confirm death by deadline
is orphaned; confirmed death with unverifiable effects is effect_unknown. Both
labels are consumed-budget decrement settlements and differ only in audit /
projection vocabulary. It then performs terminal CAS + unique
usage settlement + Receipt/Event in one transaction; late paths read the
terminal row and no-op. The coordinator owns reservation-increment-but-no-
terminal states. D3-06 product policy exposes conservative billing in the
Receipt and provides no automatic refund. Gate-G reads the process/Windows-job handle and descendant
liveness after the termination ladder; failure to confirm death is orphaned,
with cleanup outcomes in the audit Event.
