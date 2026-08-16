# Nana D2 -> D3 final gate review packet

This packet is sanitized. It uses only relative module names, test counts, and
design conclusions. It contains no user-name-bearing absolute paths, no API
keys, no environment variable values, no local IP/MAC addresses, no serial
numbers, and no credential-bearing logs.

## Review question

D2 is reported complete. Please review whether D2 meets its own exit gates and
whether it can safely hand off to D3. The user requires a strict gate: if any
unresolved issue would affect D3, the conclusion must be VETO / cannot hand off.

Please return:

- ACCEPT / VETO / unresolved for D2 completion;
- ACCEPT / VETO / unresolved for D2 -> D3 handoff;
- blocking issues, if any;
- non-blocking debts, if any;
- specific rebuttal to Codex's tentative concern about authority/evidence
  registration.

## Authoritative spec constraints

The product spec defines Nana as a local-first, evidence-traceable, high-autonomy
Research & Engineering OS. `v0.3.0-dev` D2 is scoped as
`process/action/policy/budget`.

D2 exit requirements:

- unregistered Capability cannot run;
- capability digest mismatch, args schema mismatch, provider mismatch, path,
  network, process, timeout, output and budget overrun must fail closed before
  execution where applicable;
- cancel after request must not start new Action;
- budget at 100% must prevent new Action start;
- PolicyGrant must only authorize Actions satisfying capability, args, data,
  directory, network, process, provider, budget, concurrency, uses and expiry
  constraints;
- one-time Approval must be consumed atomically and must reject replay;
- every executed terminal Action must produce Receipt preserving authorization
  source/ref, authorized effects, actual effects, effect_violation, result and
  resource usage;
- effect overrun must be `effect_violation=true` and `result=effect_unknown`;
- locked security corpus must have zero unauthorized T3/T4/T4-like passes.

D3 constraints:

- D3 may consume Action/Event/Receipt/outbox/artifact projections as facts;
- D3 must not recompute authorization from Approval/PolicyGrant;
- D3 must not bypass D2 admission/scheduler/executor;
- D3 browser SSE client must use fetch + ReadableStream, not native EventSource;
- runtime API/OpenAPI merge is a D3 decision, not hidden D2 work;
- Workspace lock lifecycle is required before real mutation serving:
  lock before writable SQLite open, reconciliation before ready, second instance
  fail closed, release lock after SQLite close.

## Current D2 implementation evidence observed by Codex

Implemented modules include:

- `contracts/common.py`
- `contracts/capabilities.py`
- `contracts/builtin_capabilities.py`
- `contracts/authorization.py`
- `contracts/safe_json_schema.py`
- `storage/schema.py`
- `storage/migrations.py`
- `storage/admission.py`
- `storage/run_scheduler.py`
- `storage/budget_accounting.py`
- `storage/locked_unittest_executor.py`
- `storage/windows_job.py`
- `locked_unittest_worker.py`
- `d2_runtime_handoff.md`

Current schema/read ceiling is 6.

Key implementation facts:

- Capability identity uses id/version/digest.
- `CapabilityRegistryEntry` includes execution ceiling:
  read_roots, write_roots, network targets/methods, env keys, process targets,
  timeout and default effect.
- Built-in `python.unittest.locked` is T2, fixed digest, provider forbidden,
  read roots `project:source` and `project:tests`, no writes, no network, no env,
  fixed process target.
- Registry rows store canonical full `entry_json + contract_digest`.
- v4 refuses old incomplete registry rows.
- v6 adds append-only `action_authorizations` binding ActionHashMaterial,
  action hash, registry contract digest, authorization source/ref and
  authorization event.
- Admission re-loads args artifact bytes, checks persisted size, authorized
  artifact budget, blob hash, canonical JSON, args hash and action hash.
- PolicyGrant and Approval authorization are performed in SQLite transactions
  with Event/outbox and consumption.
- PolicyGrant concurrency and cumulative budget are derived from persisted
  authorization/action facts, not caller-provided budget context.
- Scheduler claims only authorized Actions, reserves budget before Action start,
  and rejects budget/concurrency exhaustion.
- Running cancel no longer marks Action terminal directly. Run enters
  `paused/cancel_requested`; executor terminates/settles running Actions, writes
  Receipt and usage, then Run becomes `cancelled` or `orphaned`.
- Locked executor uses fixed argv, `shell=False`, empty child environment,
  `stdin=DEVNULL`, stdout/stderr shared cap, and args allowlist.
- On Windows, trusted worker is created suspended, assigned to Job Object, then
  resumed. Job termination is preferred. `taskkill` is only a fallback/verification
  path; if tree termination cannot be verified, result becomes unknown/orphaned.
- Worker installs Python audit guard before importing frozen test:
  denies project writes, network and child process; allows declared project read
  roots and runtime resolver roots. This is explicitly not a hostile-code sandbox.
- Receipts are written for success, failure, timeout, output cap, runner error,
  running cancel and termination failure. Effect overrun forces effect_unknown.
- Handoff fixture v3 states D3 facts, structured error codes, replay semantics,
  artifact committed/reconciled projection, effect_unknown semantics and
  Workspace lock preflight.

## Verification commands observed by Codex

All current verification below passed:

- Python compileall for sidecar/tests/scripts: OK.
- TypeScript strict check: OK.
- Full Python unittest: 269 tests OK.
- D2 modules with ResourceWarning treated as error: 55 tests OK.
- D2 security matrix: 7 tests OK, covering 460 generated scenarios:
  - 200 path/parameter injection;
  - 100 prompt-like args containment supplemental cases;
  - 50 synthetic credential canaries for child env/stdout/stderr;
  - 50 Approval/Grant change/expiry/replay cases;
  - 30 real child-process cancellation fixtures;
  - 30 malicious/invalid args artifact cases.
- D2 runtime handoff: 7 tests OK.
- D0 evidence manifest self-check: OK.

Known warning:

- Full unittest still emits one shutdown ResourceWarning attributed by D2 tests
  to legacy UI shutdown. D2-focused ResourceWarning-as-error tests pass.

## Codex tentative concerns

### Concern A: authoritative evidence registration

The authoritative spec's evidence index states that tests not registered there
must not be claimed as verified. In the current workspace, D2 evidence files and
D2 exit review exist under repo `docs/`, but the authoritative Vault files
`11_...` and `12_...` still appear to register only through D1/default-auth
補正 and do not contain D2-00..D2-07 evidence sections.

Question: Is this a D2 -> D3 handoff blocker? Codex tentative view: yes for
official project gate/signoff, because D2's technical evidence is not yet synced
to the authoritative evidence index. However it may be a documentation/evidence
publication blocker rather than a code-correctness blocker.

### Concern B: Workspace lock

D2 intentionally does not implement Workspace lock. Handoff says Workspace lock
is required before real mutation serving. Codex tentative view: not a D2 blocker,
but it blocks D3 from opening real write/mutation serving until lock lifecycle and
second-instance tests are complete. D3 can start only with read-only/replay UI,
projection work, OpenAPI/runtime merge design, and Workspace lock implementation.

### Concern C: OpenAPI/runtime merge

D2 keeps D0 baseline OpenAPI and does not expose runtime mutation route. Codex
tentative view: not a D2 blocker; D3 must explicitly decide and verify merge
before real API/UI mutation work.

### Concern D: sandbox scope

D2 locked executor is not a general hostile-code sandbox. Codex tentative view:
not a D2 blocker because D2 scope is the trusted frozen `python.unittest.locked`
narrow executor, but D3/alpha must not generalize its guarantees.

## Requested strict answer

Please be strict. If any issue means D3 would inherit ambiguity or unsafe write
behavior, return VETO for handoff and state the exact prerequisite to clear it.
