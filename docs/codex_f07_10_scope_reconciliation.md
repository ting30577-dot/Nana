# Codex independent analysis — F07-10 target scope reconciliation

Date: 2026-08-09  
Status: independent design only; not a joint decision and not an implementation
authorization.

## Authority to satisfy

The T3 fixture explicitly requires an approval-gated export of a no-sensitive
draft to a **user-selected Workspace-outside test directory**. A harness-only
directory is useful for deterministic tests but does not by itself prove that
requirement.

## Candidate interpretations

| Option | Shape | Security consequence | Codex decision |
|---|---|---|---|
| A | Keep only a harness-created allow-root | Strongly deterministic, but fails the literal T3 user-selection requirement. | VETO as final scope; retain only as test support. |
| B | During D3, the user selects one directory through the Nana launcher/CLI. The owner runtime validates it and issues a 60-minute/LocalSession-bound opaque selection id; the browser submits only that id. A post-dev native picker later replaces only the selection source, not the backend contract. | Meets user-selection without browser path injection or prematurely pulling Tauri into dev. Requires selection attestation/expiry, restart, alias and crash evidence. | **Product-owner selected; pending joint security review and implementation.** |
| C | Browser posts or accepts an arbitrary absolute path, including a Web text field, and the runtime writes there after string/path checks. | Violates the frozen browser boundary and increases path confusion, reparse traversal, TOCTOU, and accidental sensitive-write risk. | VETO. |

## Required B invariants

1. D3 selection is created by the Nana launcher/CLI from an explicit user
   choice, never by browser text, a harness pretending to be the user, or a
   PolicyGrant. The post-dev native picker must preserve this contract.
2. The raw path, live handle, clear volume/file identity and opaque token remain
   app-instance memory only. SQLite may preserve only irreversible non-locating
   identity/target commitments, expiry, ActionHash/Approval/Run/Action binding
   and Event versions. The selection expires after at most 60 minutes and no
   later than its LocalSession.
3. Approval subject includes selection identity, canonical target identity,
   content hash, capability digest, and output constraints. Any change invalidates
   the Approval.
4. Before authorization, re-resolve the directory and perform only non-writing
   identity/eligibility checks. Reject reparse components, aliases,
   non-directory targets or changed identity. The selected target must be an
   existing dedicated empty directory on a supported fixed local filesystem.
   Reject volume/profile/system/Nana roots, Workspace overlap in either
   direction, every reparse/SUBST/short-name/case/mount alias, UNC/network/
   mapped drives, known cloud-sync directories, collisions and unverifiable
   filesystems. Recheck identity and emptiness before write. F07-20 separately
   requires the durable SQLite first-write fence to commit after Approval and
   before the positive probe or any external byte.
5. Write only the fixed no-sensitive draft filename/schema; do not expose shell,
   network, arbitrary filename, or remote publish.
6. Probe failure before any external byte is `failed` with empty effects;
   proven-cleaned probe bytes are recorded as actual effects with `failed`;
   unverifiable residue or crash after the durable fence is `effect_unknown`.
   No fallback, retry, rebinding or browser-inferred success is permitted.

## Product decision and remaining joint gate

The product owner selected Option B and froze the corrected F07-20 through
F07-31 rules in `docs/d3_07_plan_aligned_decisions.md`, including the strict
fixed-local target policy and fence-before-probe ordering above. This resolves
the product interpretation but does not authorize implementation: Claude must
independently review the contract and Codex/Claude must jointly ACCEPT 07-00.
Until then, no export implementation may begin.
