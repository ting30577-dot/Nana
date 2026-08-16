# Nana D2-01 设计包（脱敏）

本文件仅包含相对文件/模块名、契约事实、本地测试结果和设计问题；不包含用户名、
绝对路径、token、网络标识、凭据、环境变量值或原始日志。

## 权威依据摘要

- `07_版本路线图与验收门槛.md` 将 `v0.3.0-dev` 的 D2 定义为
  `process/action/policy/budget`。D2 gate 是取消行为，以及锁定安全语料中的
  未授权 Action 数为零。
- `11_首个纵向切片执行清单.md` 将 D1 之后的下一批 dev 任务排序为：
  先 `scheduler/cancel`，再 `capability/policy/budget`，再 React E2E。
- Workstream 2 中仍未完成 `local scheduler`、`pause/cancel/timeout/orphan
  recovery`，以及完整结构化 runtime error 行为。
- Workstream 3 中仍未完成路径/网络/环境变量/进程限制、Run Budget、
  policy/runtime consumption、产生 Receipt 的执行、T3 export fixture，以及
  policy violation 测试。
- `12_验证记录与证据索引.md` 记录 D1 已完成，随后 D2-00 已作为
  contract/storage/auth hardening 层完成。D2-00 明确没有实现 scheduler、
  真实进程执行、capability runtime、React UI、Tauri 或 alpha.1 算法内容。

## 当前本地证据

- D2-01 前基线：`python -m compileall nana_sidecar tests scripts` 通过。
- D2-01 前基线：`python -m unittest discover -s tests -v` 通过 `206/206`。
- 已知的旧 UI shutdown `gc` ResourceWarning 仍已隔离，不阻塞 D2 scheduler。
- 当前 worktree 已有 D0/D1/D2-00 阶段的 tracked 与 untracked 改动。Codex 会保留
  这些改动，不会 reset、clean、delete 或 revert 无关文件。

## 现有实现事实

- Run state 已包含 `proposed`、`queued`、`running`、`paused`、`succeeded`、
  `failed`、`cancelled`、`timed_out`、`budget_exceeded` 和 `orphaned`。
- Action state 已包含 `proposed`、`waiting_approval`、`authorized`、`running`、
  `succeeded`、`failed`、`cancelled`、`timed_out`、`denied`、`expired` 和
  `effect_unknown`。
- Event type 已包含 `run.created`、`run.started`、`run.paused`、`run.cancelled`、
  `run.timed_out`、`run.failed`、`run.succeeded`、`run.budget_exceeded`、
  `run.orphaned`、`action.proposed`、`action.authorized`、`action.started`、
  `action.output`、`action.completed`、`action.effect_unknown`、`budget.updated`
  和 `budget.threshold_reached`。
- D2-00 已要求 `CapabilityRef` id+digest、Registry entry 校验、safe JSON schema、
  UTC 授权时间、一次性 Approval、v2 storage guards、append-only events、
  retain-only outbox、readonly preflight、readonly SSE、隐私安全 locator，以及
  `ActionReceipt.authorized_effects` 和 `effect_violation`。

## Codex 独立 D2-01 提案

Codex 提议正式 D2-01 应是持久化 scheduler admission 与 cancel/budget gate，
暂不做真实工具/进程执行。

最小实现形态：

1. 增加一个很小的 runtime/storage service，只负责 scheduler 状态迁移。
2. 在单个 SQLite transaction 中为 running Run claim 一个已经 authorized 的 Action：
   - 校验 Run 仍可运行；
   - 校验 Action 仍为 `authorized` 且属于该 Run；
   - 校验启动该 Action 不会超过冻结 Run 的 `max_actions` budget；
   - 将 Action 转为 `running`；
   - 追加 `action.started` Event 和 outbox row；
   - 分配下一个 per-Run `run_seq`；
   - 两个 SQLite connection 竞争同一个 Action 时，必须恰好一个 claim 成功。
3. 如果 claim 前冻结 Run 的 action budget 已耗尽，则原子地将 Run 转为
   `budget_exceeded`，设置 `finished_at`，追加 `run.budget_exceeded`
   Event/outbox，并且不启动新的 Action。
4. 提供 cancel transition：原子地将 non-terminal Run 转为 `cancelled`，设置
   `finished_at`，追加 `run.cancelled` Event/outbox，并取消尚未 running 的
   Action（`proposed`、`waiting_approval`、`authorized`），使后续 scheduler claim
   不能再启动它们。
5. D2-01 不处理已经 running 的 Action 的真实进程终止，因为此阶段还没有真实 child
   process。D2-01 可以把 pending Action 标为 cancelled，但不得伪造 process-tree
   kill 证据。

D2-01 明确不做：

- 不做任意 shell 字符串；
- 不 spawn child process；
- 不执行 unknown code；
- 不增加 HTTP mutation route；
- 暂不做 approval/grant consumption transaction；
- 不做外部写入/export fixture；
- 不做 React UI；
- 不做 Tauri 或 launcher/workspace-lock 实现；
- 不做 alpha.1 counterexample/benchmark/Decision。

## 给 Claude 的问题

请独立审查，并用包含 `ACCEPT`、`VETO` 或 `未达成共识` 的紧凑表格回复。

1. 根据权威文档，以上 D2-01 目标是否是 D2-00 之后正确的第一个单元？
2. D2-01 是否应该现在包含 `max_actions` budget admission gate，还是应把所有 budget
   行为都延后到后续 D2 policy/budget 单元？
3. D2-01 cancel 取消 pending Actions，同时把已经 running 的 process termination 留到
   后续 process-executor 单元，这是否正确？
4. 上述 non-goals 是否是避免违反 D2-00 和 D1 安全边界所必需的？
5. Codex 修改实现前，最小必须新增哪些测试？

如对任何项给出 VETO，请给出使设计可接受的最小具体修改。
