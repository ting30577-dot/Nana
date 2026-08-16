# D3-07 Codex-only 07-00 entry and security review

Date: 2026-08-11  
Scope: one-time Approval and controlled local T3 draft export  
Governance: `docs/d3_codex_only_governance_decision_20260811.md`

## Reviewed live seams

Codex reviewed the frozen D3-07 product decisions against the live schema v6,
command transaction engine, D2 admission service, capability registry,
Artifact store, owner-lane runtime, LocalSession and canonical projection.

The design is implementable without a second runtime, browser authority,
public `ConsumeApproval`, invented Relation type, arbitrary path, generic
process execution or T4 publish. The following implementation constraint is
mandatory: `CapabilityAdmissionService.authorize_with_approval` currently owns
its own `BEGIN IMMEDIATE`, so D3-07 must extract a private in-transaction
admission primitive. `DecideApproval(approved)` must invoke that primitive from
the one command transaction; nested transactions and a separately committed
decision are forbidden.

## Historical finding disposition

| Finding | Current disposition |
|---|---|
| F1 | D3-06 is now independently ACCEPT under current Codex-only governance; its exact T2 boundary remains unchanged. |
| F2 | Design-only status is acknowledged. This gate authorizes implementation, not a completion claim; every seam still requires executable evidence. |
| F3 | One outer `BEGIN IMMEDIATE` is mandatory; private in-transaction admission is the only approved integration. Any nested transaction or partial commit is VETO. |
| F4 | Unique Approval and Action consumption constraints are necessary but insufficient; two-connection concurrency and response-loss replay tests are mandatory. |
| F5 | Target validation must reject UNC, mapped/network drives, SUBST, reparse components, aliases, profile/system/Nana/Workspace relations and configured/common cloud-sync roots using live identity checks, not prefixes alone. |
| F6 | Only a proven supported fixed-local filesystem and atomic same-directory replace are allowed. There is no fallback, overwrite or cross-filesystem path. Probe failure classification remains fail closed. |
| F7 | Reserve → SQLite commit → finalize is explicitly a compensation protocol, not cross-resource atomicity. Restart maps no-fence to proven-zero-effect failure and any durable fence to `effect_unknown`; neither retries. |
| F8 | Renderer re-checks canonical source and draft hashes immediately before fence/execution. Fifty fixed export credential canaries must have zero matches. |
| F9 | The report and Receipt provenance must bind the frozen Finding revision, producer Run, source Artifact hash, draft Artifact hash and renderer digest; mismatch is terminal rejection before external bytes. |

## Authorization boundary

This review authorizes only implementation of stages 07-01 through 07-05.
Implementation proceeds in this order:

1. schema and typed Approval command with atomic approved/denied semantics;
2. exact `export.draft_external` registry entry, `grantable=false` and
   `one_time_approval` only;
3. process-memory selection registry plus real interactive launcher boundary;
4. deterministic public-only renderer and Workspace Artifacts;
5. durable fence, fixed-local probe/atomic replace executor, Receipt and
   restart reconciliation;
6. full security matrix, no-edit scan, repairs and evidence synchronization.

The browser may submit only `command_id`, canonical expected revision,
`finding_id` and opaque `target_selection_id` when requesting export, and only
`command_id`, Approval id/revision, frozen subject hash and approved/denied
when deciding. It never supplies capability, Run/Action/Artifact ids, path,
filename, bytes, hash, data class, risk, effects or authorization reference.

## 07-00 decision

**Codex-only 07-00 design/security gate: ACCEPT FOR IMPLEMENTATION.**

`implementation_authorized` may become true. `capability_registered` and
`filesystem_write_authorized` remain false until their implementations and
focused security evidence exist. No current route may perform an external
write merely because this design gate passed.
