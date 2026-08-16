# Codex independent test matrix — F07-10 target selection

Status: planning only; no filesystem writer is enabled.

| Case | Setup | Required result |
|---|---|---|
| S1 valid user selection | User selects a regular Workspace-outside directory through Nana launcher/CLI; owner runtime validates it and issues an opaque selection; identity unchanged | Selection can be summarized for Approval; no external write before authorization |
| S2 browser path injection | Browser submits an absolute path, Web text-field path, or traversal string instead of a selection id | Typed validation rejects; no lookup or write |
| S3 selection actor mismatch | Selection id belongs to another actor/session | `E_POLICY_DENIED`/structured conflict; no authorization |
| S4 selection expiry | Selection exceeds 60 minutes, LocalSession ends, or it expires before Approval | Fail closed; close the selection; no capability registration or write |
| S5 Workspace overlap | Selected directory resolves inside or aliases canonical Workspace | Reject, including junction/reparse alias |
| S6 reparse component | Directory or ancestor is symlink/junction/reparse | Reject before Approval and again before write |
| S7 identity changed | Directory is replaced after selection but before authorization | Canonical identity mismatch; deny |
| S8 read-only eligibility unknown | Selection-time non-writing checks cannot establish basic target/volume eligibility | Reject selection or Approval request; no external write |
| S9 target/content drift | Fixed target identity or content hash changes after Approval | ActionHash mismatch; approval cannot be consumed |
| S10 crash before write | Crash before temp creation or before replace | Durable denial/cancellation; no success Receipt |
| S11 crash after write begins | Crash after temp/write/replace boundary | `effect_unknown`; no retry/resume/dismiss/success mutation |
| S12 response loss | Commit succeeds but HTTP response is lost | Command replay returns stored result; no second consumption |
| S13 non-public or secret fixture | Any renderer input is not canonically `public`, has mixed/unknown classification, or the draft contains a forbidden canary | Reject before Export subject/write; escaping is never treated as privacy sanitization; no external bytes |
| S14 double submit | Two competing `DecideApproval(approved)` requests race | One durable decision/authorization/internal consumption; second replay/conflict, never double effect |
| S15 unauthorized positive probe | Instrument target directory before Approval/authorization | Zero create/write/rename/delete operations; any attempted probe fails the gate |
| S16 authorized positive probe unsupported | Approval/consumption and durable first-write fence commit, then the real probe cannot prove the primitive | Before-byte failure: `failed` with empty effects; proven-cleaned probe: `failed` with recorded effects; unverifiable residue/crash: `effect_unknown`; no report, fallback, retry or rebind |
| S17 dangerous target | Selection is a volume/profile/system/Nana root, Workspace ancestor/descendant, reparse/alias, UNC/network/mapped/cloud-sync target, non-fixed/unsupported filesystem, non-empty directory, collision or changed target | Reject before issuing/binding selection or before write as applicable; fixed filename and no overwrite; zero report bytes |
| S18 invalid export source graph | Finding is not produced by the selected terminal algorithm Run, or source Artifact lacks that Run's producer edge | Reject before Export Run/Action/Approval creation; no invented RelationType |
| S19 report renderer drift | Renderer version/template, normalized Finding bytes, source Artifact hash, or produced draft hash differs from the frozen contract | Reject or create a new Action subject; old Approval cannot authorize changed bytes |
| S20 denied/expired Run convergence | Denial/expiry commits, then process crashes before Export Run terminalization | Minimal Approval transaction remains unchanged; deterministic system `CancelRun` converges exactly once after restart |
| S21 request preparation crash | Draft Artifact commits inside Workspace, then failure occurs before Export Run/Action/Approval transaction | No external bytes; retry reuses verified content-addressed Artifact and creates one subject graph/CommandResult |
| S22 browser subject injection | Browser adds Run/Artifact/Action/capability/hash/effect/path/filename fields to the narrowed request | Strict schema rejects; owner derives every subject/security field and performs no external write |
| S23 ambiguous source graph | Finding has no unique terminal producer Run, or that Run has zero/multiple eligible D3-06 result Artifacts | Fail closed before report rendering or Export subject creation; no browser choice resolves ambiguity |
| S24 restart while Approval requested | Process restarts after Export subject commit but before decision; in-memory selection is gone | Typed expiry + deterministic Run cancellation; no path rebinding and no external bytes |
| S25 restart after approval, before write fence | Approval is approved/consumed and Action authorized or claimed, but no durable write/probe fence exists | Prove target instrumentation saw zero operations; failed Receipt with empty actual effects, budget settled once, Export Run failed, no reselect/resume/retry |
| S26 restart after write fence | Durable first-write/probe fence exists when owner is lost, including a fault injected between fence commit and the first OS write | Conservatively `effect_unknown` because process-local selection/effect proof is gone; terminal Run, no rebind/retry/success inference |
| S27 selection reservation race | Two request ids race for one available selection | Owner lane reserves one `(command_id, request_hash, Run/Action ids)`; other rejects; no duplicate subject |
| S28 memory/SQLite crash windows | Inject crash before reserve, after reserve, during rollback, after SQLite commit before finalize, and after response loss | Exact F07-31 convergence; stored result replay never rebinds another Action |
| S29 CLI/harness provenance | Real interactive selection and injected temporary test root are each started | Handshake labels real user selection versus `test_harness`; harness can never satisfy real-user E2E |
| S30 Windows identity alias | Same directory is addressed via case/short-name/SUBST/mount alias or component replacement | Handle identity detects equality/change; dangerous/Workspace overlap and reparse rules fail closed |
| S31 selection lifetime | Selection reaches the 60-minute/LocalSession ceiling, terminates, drains, or a second Export attempt reuses its id | Reject/close exactly once; Approval expiry never exceeds selection expiry; fresh attempt requires a fresh selection and Export chain |

## Required evidence shape

Each case must capture the canonical ActionHash material, selection identity
classification, Approval/authorization/consumption rows, Event/outbox ids,
before/after Artifact state, Receipt result, and absence/presence of bytes in the
test directory. Paths must be represented by non-sensitive test labels in the
evidence packet; no user paths or credentials may be sent to Claude.
The evidence must also include canonical data-class proof, the durable
first-write-fence Event/row ordering relative to every instrumented directory
operation, fixed-local filesystem classification, and proof that no clear
volume/file identity or opaque token escaped process memory.
