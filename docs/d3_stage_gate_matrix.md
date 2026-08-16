# D3 stage gate matrix

Date: 2026-08-09

Every implementation stage requires: accepted design gate, implementation,
pre-edit finding scan, consolidated repair, focused/full verification, final
no-edit scan, evidence synchronization and independent exit review.

| Stage | Boundary | Current state | Next gate |
|---|---|---|---|
| D3-00 | frozen D3 contracts and R1-R4 boundaries | ACCEPT | complete |
| D3-01 | OS Workspace lock lifecycle/reconciliation | ACCEPT | complete |
| D3-02 | sole authenticated runtime/OpenAPI authority | ACCEPT | complete |
| D3-03 | canonical projection/SSE/replay | ACCEPT | complete |
| D3-04 | read-only React cockpit/browser SSE | ACCEPT | complete |
| D3-05 | typed canonical journey writers | ACCEPT | complete |
| D3-06 | exact locked T2 worker bridge | F-14..F-35 repaired; current Codex-only independent ACCEPT | complete under 2026-08-11 governance |
| D3-07 | one-time Approval and controlled local T3 draft export | Codex-only ACCEPT; F07-32..F07-41 repaired and exit evidence synchronized | complete |
| D3-08A | core mutation UI/negative-state usability | Codex-only ACCEPT; F08A-01..F08A-13 closed | complete |
| D3-08B | Approval/export/Receipt UI | Codex-only ACCEPT; F08B-01..F08B-10 closed | complete |
| D3-09 | complete dev journey/release evidence | Codex-only ACCEPT; 10/10 complete journeys, 25/25 release matrix, F09 closed | complete |

## Non-negotiable sequencing

1. Historical Claude material remains historical evidence only. Under the
   2026-08-11 governance decision, Codex is the sole current stage authority;
   no missing Claude result is treated as ACCEPT or VETO.
2. D3-07 received a fresh Codex-only 07-00 entry ACCEPT and a separate
   implementation exit ACCEPT. Its exact T3 registration and fixed-local writer
   do not authorize any broader capability or target.
3. D3-07 uses an independent Export Run, launcher/CLI-issued opaque target
   selection and the narrow T3 candidate `export.draft_external`; it never
   reopens the terminal algorithm Run or reuses T4 `export.publish`.
4. `DecideApproval(approved)` is the sole public approval path that atomically
   decides, authorizes and internally consumes; `denied` never authorizes or
   consumes, and no public `ConsumeApproval` exists.
5. F07-20 freezes read-only selection, atomic Approval, durable first-write
   fence before probe/bytes, three failure classes and no fallback/retry/rebind;
   current Codex review and executable evidence are still required.
6. F07-21 freezes the existing dedicated empty supported fixed-local target and
   exact root/system/Nana/Workspace/reparse/alias/UNC/network/cloud/collision/
   change rejection; fixed filename/no overwrite.
7. F07-22 through F07-25 freeze the existing typed provenance graph+snapshot,
   server-derived application composition, separate deterministic denied/
   expired convergence and exact public-only deterministic report Artifact.
8. F07-26 through F07-31 freeze memory-only raw target authority, irreversible
   durable commitments, retained-handle Windows identity, 60-minute one-use CLI
   selection, restart classification and explicit compensation protocol.
9. D3-08B consumes canonical Approval/Receipt facts and may not invent them in
   browser state.
10. D3-09 may not waive an unresolved finding, missing independent review or
    corrupted package evidence.
11. The historical stop-after-D3-07 boundary is superseded. Continue in order
    through D3-08A, D3-08B and D3-09 only after each real predecessor exit.

The machine-readable D3-07 gate retains historical joint status while recording
the current Codex-only implementation exit:

```text
joint_status=unresolved
implementation_authorized=true
capability_registered=true
filesystem_write_authorized=true
```
