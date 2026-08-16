# Claude D3-06 design response (sanitized)

Date: 2026-08-08. Review of the first D3-06 design packet; no implementation
authorization was granted.

## Decision

Q1 boundary and staged delegation: NOT YET CONSENSUS.

## Evidence and objections

Claude agreed the server-owned fixture, execution-time digest check, closed
browser command union, single D3-to-D2 admission handoff, and D2-owned
matching/consumption/authorization facts materially reduce injection risk. It
did not accept sufficiency because four contract points were unstated:

1. authenticated subject authorization to the target Project/Inquiry/Plan;
2. the trusted source and binding of the StartRun idempotency key;
3. CancelRun target lookup and cross-scope authorization;
4. crash compensation between D2 grant consumption and scheduler budget
   reservation.

## Required repair applied

The Codex design now states that owner-lane subject authorization fails closed
before Run/Action creation, binds idempotency to actor + target + exact
revision + fixture digest, restricts cancellation to a server-issued Run ID
with an actor-scope check, and reconciles authorized-but-unclaimed Actions to
one terminal fact without re-admission/reclaim. Grant consumption is explicitly
an intentional durable admission fact; refunds require an out-of-scope D2
release API.

This response remains historical evidence. D3-06 is still NOT YET CONSENSUS
until Claude reviews the repaired packet and the lifecycle/bridge gates.

## Slice-B review (historical)

Claude also returned NOT YET CONSENSUS for the lifecycle slice. The objections
were: a claim-to-spawn cancellation race, missing replay semantics while a
command is still in flight, timeout absent from the durable state vocabulary,
and undefined Artifact visibility / budget direction for effect_unknown.

The Codex repair now adds an owner-lane compare-and-set spawn fence,
non-terminal replay returning current durable state without blocking, explicit
`timed_out`, and conservative usage commit plus post-commit labelled Artifact
visibility for timeout/effect_unknown/orphaned paths. Pre-spawn cancellation
releases the reservation; post-fence cancellation cannot be downgraded to
cancelled.

## Slice-C review (historical)

Claude's gate-by-gate result was Gate-A/B/C/E ACCEPT with conditions,
Gate-D/F NOT YET CONSENSUS, and two missing mandatory gates: Gate-G for
termination confirmation/resource reaping and Gate-H for auditable gate
decisions. The objections were an unstated same-snapshot check-and-use rule,
effect_unknown budget direction, watchdog ownership of timeout, structural
proof of no worker SQLite handle, and termination confirmation.

The Codex repair adds all of those as explicit Gate-A through Gate-H
requirements: immutable verified bytes, D2 process-segment extraction, no
release for uncertain effects, owner-lane watchdog, no DB handle in worker,
confirmed residue semantics, and tamper-evident decision Events.

## Final compact-packet review (historical)

Claude returned NOT YET CONSENSUS because the compact packet still lacked
auditable evidence for the CAS fence state table, exactly-once reservation
assertions, and Gate-G's confirmed-residual input. The Codex design now records
those state transitions and assertion points explicitly: conditional writes on
one Action state, one reservation increment/decrement by causation ID, and
process/job plus descendant liveness as the Gate-G decision source. A new final
Claude verdict is required before implementation.
