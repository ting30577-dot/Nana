# Codex independent design — D3-07 controlled T3 export

Status: design only; implementation is not authorized. This proposal is
relative-path and fixture-only. It is intentionally separate from the current
Codex-only VETO gate so Claude can challenge it independently.

## Proposed canonical flow

1. After the algorithm Run is terminal and the Finding plus source Artifact are
   canonical, a separate Export Run and exact T3 Export Action are created. The
   Export Run snapshot freezes the source algorithm Run, Finding, source
   Artifact/content hash, target selection identity, capability digest, effect
   ceiling and budget. Canonical Relations preserve the provenance; the
   terminal algorithm Run is never reopened.
2. The closed journey/application `RequestApproval` contains only command id,
   Finding id/current aggregate Event version and opaque selection id. The owner
   derives the source graph, exact draft Artifact, independent Export Run,
   Action, capability, ActionHash/effects/budget and Approval subject. The
   browser cannot submit any of those derived fields, a path or arbitrary bytes.
3. The owner lane persists the proposed Approval subject `(action_id,
   action_hash)` and deterministic composite result through the accepted
   Artifact/Command transaction protocols.
4. `DecideApproval(decision="approved")` binds the decision to the immutable
   Approval subject and, in the same D2 admission-owned transaction, writes
   durable authorization, one-time `approval_consumptions`, Approval/Action
   Events and outbox rows, plus the stable command result. A public
   `ConsumeApproval` command does not exist. `denied` writes only the terminal
   decision, its Event/outbox and result, never authorization or consumption.
5. After approval/consumption, the owner lane commits a durable first-write
   fence before the real probe or any external byte. The export worker receives
   immutable bytes and a server-resolved target descriptor only. The owner lane
   performs preflight/fence, completion, Receipt and budget settlement. The
   worker has no SQLite handle.

## Capability and target contract

- Capability candidate is the existing contract-test name
  `export.draft_external`, never the T4 `export.publish`; it has T3 risk, one-time
  Approval mode, `grantable=false`, provider forbidden, network empty, and a
  digest-pinned registry entry. It remains unregistered until the joint gate.
- During D3, the user selects one Workspace-outside test directory through the
  Nana launcher or CLI. The owner runtime canonicalizes and validates it, then
  issues a 60-minute/LocalSession-bound actor/session-bound opaque selection id. The browser
  receives only that id, a redacted display label and expiry, never an absolute
  path. The maximum lifetime is 60 minutes and the owning LocalSession; one id
  binds exactly one Export Run/Action/attempt.
  The deterministic harness root remains test support and is not presented as
  user selection. A target is accepted only if every existing path component
  is a regular non-reparse child, the resolved path remains below the selected
  root, filename/media type/size are exact, the target has not changed since
  approval. It must be an existing dedicated empty directory on a supported
  fixed local filesystem and reject roots/profile/system/Nana/Workspace overlap,
  every reparse or identity alias, UNC/network/mapped/cloud-sync targets,
  collision and change. The fixed filename is never overwritten.
- Selection-time checks must not write outside Workspace. The real positive
  atomic-replace probe runs only after Approval/consumption and durable
  first-write-fence commit. Before-byte failure is empty-effect `failed`; proven
  cleaned probe bytes are recorded as `failed`; unverifiable residue/crash is
  `effect_unknown`. The report proceeds only after success; no non-atomic
  fallback, retry or target rebinding exists.
- ActionHashMaterial includes capability digest, exact arguments, target
  identity, source content hash, requested effects, T3 risk, budget and
  reversibility. Before/after Artifact ids and hashes are Receipt facts.

## Failure and replay semantics

- Same command id/request hash replays the stored result; a changed hash is a
  structured conflict with no new Approval or Action.
- Subject hash mismatch, content/target mutation, expiry, duplicate
  consumption, unsupported atomic replace, and changed target fail closed before
  write.
- With no durable first-write fence, restart settles authorized/claimed work as
  `failed` with empty effects. With the fence, owner loss or unverifiable replace
  is `effect_unknown`; neither UI nor retry may project success, rebind a target
  or silently refund budget.
- Approval pending/denied/expired, authorized/running, effect_unknown and
  Receipt are canonical read-model states. The UI never fabricates completion.

## Explicit independent-review questions for Claude

1. Does keeping raw path/handle/token/clear identity in app memory while
   persisting only irreversible non-locating commitments preserve portability,
   privacy, replay and restart fail-closure?
2. Does the frozen Approval→durable first-write fence→probe ordering, including
   its three failure classes, prove zero unapproved effects without overstating
   fence-as-proof-of-write?
3. What exact Windows atomic-replace probe and crash injection points satisfy
   Gate-G without overclaiming generic hostile-code sandboxing?
4. Which before/after Artifact commitment facts must be written before versus
   after the external replace to preserve conservative reconciliation?
5. Does the frozen fixed-local/empty target policy completely reject roots,
   system/Nana/Workspace overlap, reparse/aliases, UNC/network/cloud sync,
   collision/change and unverifiable filesystems without hidden path leakage?
6. Does the product-frozen existing-edge graph in
   `docs/codex_d3_07_export_subject_audit.md` satisfy the product requirement,
   or is an explicit Relation Registry extension required for F07-22?
7. May a narrowed browser `RequestApproval` application request compose the
   existing canonical `StartRun`/`ProposeAction`/`CommitArtifact`/
   `RequestApproval` semantics without introducing a new canonical Command?
8. Does a separate deterministic system `CancelRun` after a denied/expired
   Approval preserve the minimal denied transaction while closing F07-24?
9. Does the product-frozen public-only deterministic Markdown renderer,
   provenance and 50-canary contract close F07-25 before bytes/hash are bound?

Codex decision: `docs/d3_07_plan_aligned_decisions.md` freezes the Approval,
independent Export Run, public-only renderer, fixed-local selection, 60-minute
one-use lifetime, durable-fence and restart/coordination rules. This remains a
planning proposal, not an implementation ACCEPT; the questions above ask Claude
to challenge those decisions, and joint 07-00 ACCEPT is still required before
code.
