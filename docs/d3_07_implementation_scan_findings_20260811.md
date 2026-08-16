# D3-07 implementation and no-edit scan findings

Date: 2026-08-11  
Scope: one-time Approval and exact local T3 `export.draft_external`

Codex reviewed the live schema, runtime, selection registry, admission seam,
export executor, canonical projections and executable tests after implementation.
Historical Claude files were used only as gap prompts; no historical verdict was
treated as current acceptance.

| Finding | Severity | Live-worktree issue | Repair and direct evidence |
|---|---:|---|---|
| F07-32 | P1 | A replayed prepare command could reserve a selection before consulting `command_log`. | Replay now preflights the durable command and returns the stable result without requiring live selection authority; response-loss/closed-selection replay is tested. |
| F07-33 | P1 | Expiry could reject a decision without deterministically converging its Export Run/Action. | The rejection transaction records `approval.expired`; the caller and startup reconciler idempotently cancel the waiting Run/Action with no authorization, consumption, Receipt or write. |
| F07-34 | P1 | Selection identity needed revalidation around every external operation, not only at approval. | The retained identity is checked before probe, after probe creation, before report creation, before final rename and after final rename. Any unverifiable post-fence state is `effect_unknown`. |
| F07-35 | P1 | `INSERT OR IGNORE` alone could silently accept a conflicting capability row. | Preparation reloads and byte-compares the exact persisted registry JSON and contract digest before creating the subject. |
| F07-36 | P2 | Directory iterators and failed SQLite configuration paths could leak handles during failure/retry. | Every `scandir` is context-managed; SQLite open helpers close on configuration failure; strict `ResourceWarning` suites pass. |
| F07-37 | P1 | Content-addressed draft deduplication could bind a second attempt to the first Export Run producer. | Each export attempt has a deterministic independent draft Artifact id bound to its own Run; preparation retry repairs staged artifacts without duplicating the subject. |
| F07-38 | P1 | A runtime without a selection registry could advertise Approval commands or surface an internal error. | Handshake command availability is capability-aware and disabled Approval requests return structured 422 before `command_log`; authenticated runtime coverage proves the enabled path. |
| F07-39 | P1 | Frozen Artifact/source validation had to complete before the first-write fence. | The executor loads only durable D2 authorization, verifies the canonical source, renderer, args and draft hash, then commits the fence; pre-fence failures settle with empty actual effects. |
| F07-40 | P1 | Exact cloud-folder names missed branded variants, and a retained Windows directory handle did not prove rename prevention on every supported build. | Cloud components now reject bounded OneDrive/Dropbox/Google Drive/iCloud/Box/SharePoint variants. Real Windows tests prove rename is detected by identity revalidation; the implementation no longer claims the handle alone prevents replacement. Post-write mismatch is never success. |
| F07-41 | P2 | Abrupt owner termination exposed a Windows WAL/SHM reopen race as transient SQLite `disk I/O error`. | While the Workspace OS lock is held, initialization performs a short bounded retry only for that exact transient error. Other SQLite failures remain immediate and fail-closed; the real process-crash restart test passes. |

## Final scan result

- No public `ConsumeApproval`, `PublishExport`, T4 publish route, arbitrary
  shell/Python, network target or browser path/bytes/capability selector was
  introduced.
- Raw target path, live handle, clear volume/file identity and opaque selection
  token remain process-memory-only. SQLite stores irreversible commitments.
- Approved decision, durable authorization, one-time consumption, events,
  outbox and stable command result share one outer `BEGIN IMMEDIATE` transaction.
- Denied, expired, replay and changed-subject paths cannot authorize or consume.
- The first external byte remains after a durable fence; post-fence uncertainty
  is `effect_unknown`, terminal and non-retryable.
- D2 `python.unittest.locked` remains the only T2 execution bridge and is not
  described as a hostile-code sandbox.

**No unresolved D3-07 implementation finding remains.**
