# Nana v0.3.0-dev-D3 handoff - start here

> Historical handoff. For all current status and verification, use
> [`docs/CURRENT_D3_AUTHORITY.md`](docs/CURRENT_D3_AUTHORITY.md).

Snapshot date: 2026-08-10  
This file describes current workspace truth and does not replace the
authoritative specifications.

> Superseded status notice (2026-08-13): the stage table and hard-gate section
> below are retained as the historical 2026-08-10 handoff. D3-07 through D3-09
> were subsequently implemented, but the later full-D3 ACCEPT was itself
> reopened after the product launcher was found to print Bearer credentials,
> use a fixed default port and lack a normal browser bootstrap. Those entry
> defects are repaired in the live worktree; Pause/Resume, failed→retry_of and
> the refreshed manifest-backed release gate remain open. Use Vault documents
> 07/10/11/12 as current authority, not the historical stage table below.

## Single-file continuation contract

A new main conversation may start by reading this file, then must inspect the
listed files before changing anything. The project workspace is
`C:\Users\q1968\Desktop\Nana`.

The authoritative Nana specifications are in the Obsidian Vault directory
`D:\Obsidian Vault\Nana_研究系统` and are not copied into this workspace as the
source of truth. The complete required specification set is:

- `D:\Obsidian Vault\Nana_研究系统\00_Nana_总览与导航.md`
- `D:\Obsidian Vault\Nana_研究系统\05_技术架构与数据契约.md`
- `D:\Obsidian Vault\Nana_研究系统\06_AI自治_安全与隐私.md`
- `D:\Obsidian Vault\Nana_研究系统\07_版本路线图与验收门槛.md`
- `D:\Obsidian Vault\Nana_研究系统\10_完整性_可行性_可执行性终审.md`
- `D:\Obsidian Vault\Nana_研究系统\11_首个纵向切片执行清单.md`
- `D:\Obsidian Vault\Nana_研究系统\12_验证记录与证据索引.md`

For this continuation, GPT independently owns planning, implementation,
review, verification, and evidence synchronization. Claude is not required:
do not call, retry, wait for, or treat historical Claude packets as a new
decision. This instruction does not weaken any Nana security gate.

Before implementation work, also read `AGENTS.md`, this handoff, the current
D3 plan/decision files, the D3 completion audit and stage-gate matrix, and the
canonical D3-07 gate record listed below. Preserve the dirty worktree; never
reset, checkout, clean, or delete unrelated files.

## Required read order

1. `AGENTS.md`
2. All seven authoritative Vault documents listed above: `00`, `05`, `06`,
   `07`, `10`, `11`, and `12`
3. `docs/d3_full_plan_and_boundaries.md`
4. `docs/d3_full_plan_decision_record.md`
5. `docs/d3_completion_audit.md`
6. `docs/d3_stage_gate_matrix.md`
7. `docs/d2_runtime_handoff.md`
8. `docs/d2_07_exit_review.md`
9. `docs/d2_07_decision_record.md`
10. `docs/evidence/v0.3.0-dev-d2-manifest.txt`
11. `docs/evidence/v0.3.0-dev-d2-manifest.sha256`
12. `fixtures/v0.3.0-dev/d2_runtime_handoff_replay.json`
13. `fixtures/v0.3.0-dev/d2_security_matrices.json`
14. `docs/d3_06_third_scan_findings.md`
15. `docs/d3_06_reopening_batch_repairs.md`
16. `docs/d3_06_final_scan.md`
17. `docs/evidence/v0.3.0-dev-d3-06-completion.md`
18. D3-07 decision/gate documents listed below

## Claude 协作通道（新对话必须先读）

Claude 不是通过官方 Anthropic API 或官方 CLI 接入 Nana。Nana 的唯一调用入口是：

```powershell
.\.venv\Scripts\python.exe .\scripts\ask_claude.py `
  "请独立审查指定议题，并明确 ACCEPT、VETO 或尚未达成共识。" `
  --context .\docs\claude_d3_06_implementation_exit_packet_sanitized.md
```

该脚本内部调用 `nana_core.ai.ClaudeReviewer`，只读取以下三个中转站变量：
`NANA_CLAUDE_API_KEY`、`NANA_CLAUDE_BASE_URL`、`NANA_CLAUDE_MODEL`。实际网络请求
发往 `NANA_CLAUDE_BASE_URL` 指定的 Anthropic 兼容中转站；`ANTHROPIC_API_KEY`
不会被读取，官方 `api.anthropic.com` 地址会被拒绝。缺少中转站配置时，程序应
直接失败并诊断配置，不得改走官方接口。

隐私与授权边界：不要把 Key、环境变量值、用户名、机器信息或日志凭据发送给
Claude；只发送脱敏的相对路径上下文。不要运行会要求官方 API Key、OAuth 或
其他外部授权的命令。若新对话提出这类授权请求，先停止并回到
`docs/claude_collaboration.md` 的中转站检查，不要授权，也不要让我代为转发。

若中转站调用失败，Codex 应直接检查 `scripts/ask_claude.py`、
`nana_core/ai/claude_reviewer.py` 及连接错误证据，并记录为阻塞；不能让用户另开
PowerShell，也不能自行切换到官方通道。

注意：`docs/evidence/*claude-cli-preflight*`、`*claude-cli-result*` 是历史性的
first-party/OAuth 隔离实验记录，不是当前通道。不要执行其中的 OAuth 步骤，也
不要再次向用户索取授权；当前授权只覆盖指定脱敏包通过 Nana 中转站发送。

## Current continuation boundary

For the current development continuation, the product owner explicitly
requested that Codex not call, retry, or wait for Claude. Historical Claude
packets and transport records remain evidence only; they are not a new review
verdict. Continue with local source inspection, tests, runtime checks and
evidence synchronization. Do not change the D3-07 gate flags to compensate for
the absent independent review.

## Product boundary

The intended D3 journey is:

`create -> provenance -> editable Plan -> locked T2 test Run -> Activity -> Artifact -> Finding draft -> one-time Approval -> controlled T3 draft export -> Receipt`

D3 consumes canonical D2 facts. The browser never derives authorization,
executes arbitrary shell/Python, or directly writes files. The locked unittest
fixture is not a hostile-code sandbox.

## Stage truth

| Stage | Current truth |
|---|---|
| D3-00..D3-05 | accepted exits recorded |
| D3-06 | reopened findings F-14..F-32 repaired; 17 focused, 123 strict D3, 386 full Python, 58 Vitest and 17 read-only browser E2E tests pass; Codex local ACCEPT; Claude exit still absent |
| D3-07 | planning only; 07-00 joint gate unresolved; implementation disabled |
| D3-08A/08B | planning only |
| D3-09 | planning only; ten-run/release evidence absent |

## Hard gates

- Do not implement D3-07 until both the D3-06 independent exit and D3-07
  07-00 joint gate are ACCEPT.
- Do not register T3 capability, add Approval/export mutation routes or write
  outside Workspace before those gates.
- Do not infer authorization in UI state or report optimistic success.
- Browser SSE remains authenticated `fetch` plus `ReadableStream`, not native
  `EventSource`.
- Post-write uncertainty is `effect_unknown`/orphaned according to canonical
  liveness evidence and is never silently retried.

## D3-06 current evidence

- Current review packet:
  `docs/claude_d3_06_implementation_exit_packet_sanitized.md`
- External-review status:
  `docs/d3_06_claude_exit_blocker.md`
- Scoped completion evidence:
  `docs/evidence/v0.3.0-dev-d3-06-completion.md`

The packet passed a local privacy scan. The product owner explicitly authorized
the exact D3-06 and D3-07 packets. The configured Nana gateway request for the
revised question passed all hash checks but exhausted its adapter retries with
a connection failure. No ACCEPT, VETO or structured verdict exists. See
`docs/evidence/v0.3.0-dev-d3-07-claude-reprompt-gateway-result.md`.

The latest local regression and manifest refresh is recorded in
`docs/evidence/v0.3.0-dev-d3-local-regression-and-manifest-refresh-20260810.md`.

## D3-07 gate evidence

- `docs/d3_07_stage_decomposition_draft.md`
- `docs/d3_07_entry_gate_decision_record.md`
- `docs/evidence/v0.3.0-dev-d3-07-gate-decision.json`
- `docs/d3_07_runtime_surface_audit.md`
- `docs/d3_07_design_consistency_repair.md`
- `docs/codex_f07_10_scope_reconciliation.md`
- `docs/codex_f07_10_test_matrix_design.md`
- `docs/d3_07_plan_aligned_decisions.md`
- `docs/evidence/v0.3.0-dev-d3-07-claude-preflight.md`
- `docs/evidence/v0.3.0-dev-d3-07-claude-gateway-attempt.md`
- `docs/evidence/v0.3.0-dev-d3-07-claude-cli-result.md`
- `docs/evidence/v0.3.0-dev-d3-07-claude-reprompt-result.md`
- `docs/evidence/v0.3.0-dev-d3-07-claude-reprompt-gateway-result.md`
- `docs/evidence/v0.3.0-dev-d3-07-claude-relay-only-retry-20260809.md`
- `docs/evidence/v0.3.0-dev-d3-authority-sync-summary.md`
- `docs/evidence/v0.3.0-dev-d3-07-claude-relay-retry-20260810.md`
- `docs/d3_07_implementation_readiness_matrix.md`
- `docs/d3_07_entry_gate_decision_record.md` (current local continuation note)
- `docs/evidence/v0.3.0-dev-d3-07-readiness-audit-20260810.md`
- `docs/codex_d3_07_transaction_integration_map.md`
- `docs/codex_d3_07_export_subject_audit.md`
- `docs/codex_d3_07_selection_registry_audit.md`
- `docs/claude_d3_07_entry_gate_packet_sanitized.md`

F07-10 and its related product questions are now frozen at the design level:
the user selects a Workspace-outside test directory through the Nana
launcher/CLI; the owner runtime validates it and gives the browser only a
60-minute/LocalSession-bound opaque selection id plus a redacted label. A harness root remains
test support and may not masquerade as user selection; a native picker remains
post-dev. Approval uses canonical `approved`/`denied`, with
`DecideApproval(approved)` atomically deciding, authorizing and internally
consuming; there is no public `ConsumeApproval`. Each attempt owns an
independent Export Run linked to the terminal algorithm Run, Finding and source
Artifact.

`docs/d3_07_plan_aligned_decisions.md` now product-freezes F07-20 through
F07-31. Selection checks are read-only; after atomic Approval/consumption a
durable first-write fence must commit before the real probe or any external
byte. Before-byte failure is empty-effect `failed`, proven-cleaned probe effects
are recorded, and unverifiable residue/crash is `effect_unknown`; no fallback,
retry or rebinding is allowed.

The target is an existing dedicated empty directory on a supported fixed local
filesystem. Root/profile/system/Nana/Workspace overlap, every reparse/identity
alias, UNC/network/mapped/cloud-sync target, collision/change and unverifiable
filesystem are rejected; filename is fixed and overwrite forbidden. The
existing Relation graph plus frozen Export Run snapshot is used, the narrow
application request derives all security subjects server-side, denial/expiry
converges through deterministic system `CancelRun`, and only canonical `public`
inputs enter the exact fixed Markdown renderer.

Raw path, handle, opaque token and clear volume/file identity remain process
memory only; durable records contain only irreversible non-locating commitments
and normal subject/binding/version facts. Selection lifetime is at most 60
minutes and its LocalSession, one Export Run/Action/attempt. Memory reservation
and SQLite use reserve→commit→finalize compensation, explicitly not
cross-resource atomicity. These are product decisions only: Claude review,
joint 07-00 ACCEPT and implementation evidence remain missing, so all write
flags stay false.

Execution boundary: the user directed the current development run to pause once
D3-07 is fully completed and accepted. Do not begin D3-08A, D3-08B or D3-09 in
this run; their existing files remain future planning only.

## Package status

The sibling ZIP and same-name extracted directory were regenerated after the
latest D3 relay-retry evidence. `PACKAGE_MANIFEST_SHA256.txt` contains 600
source-file entries with zero missing/hash errors; the directory and ZIP each
contain 605 files and compare equal by path and SHA-256. The package remains a
handoff snapshot, not permission to bypass the D3-07 joint gate.

The live workspace is authoritative for the current task. Preserve its dirty
worktree and do not overwrite unrelated user changes.
