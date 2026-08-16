# Nana D2-05 设计包（脱敏）

目标：把 D2-01 的 count gate 与 D2-03 admission budget context 扩展为真实 runtime budget accounting。本包只包含相对模块名、阶段事实和设计问题，不包含用户名、绝对路径、token、环境变量值、内网地址、MAC、设备序列号、软件授权或未脱敏日志。

## 已完成前置

- D2-01 已有 `RunSchedulerService.claim_action(...)`：
  - 只 claim `authorized` Action；
  - 在同一 SQLite transaction 中把 Action 转为 `running`；
  - 已用 `max_actions` count gate 阻止超发；
  - budget exhaustion 当前使用 `run.budget_exceeded` 事件和 Run terminal state `budget_exceeded`。
- D2-03b 已有 admission service：
  - 绑定 ActionHashMaterial、persisted Action、args artifact、registry entry、policy grant / approval；
  - grant/approval consumption 原子化；
  - 不执行真实工具。
- D2-04 已有 `LockedUnittestExecutorService`：
  - 通过 scheduler claim authorized Action；
  - 执行 frozen `python.unittest.locked`；
  - 产生 `ActionReceipt.resource_usage`；
  - receipt/event/outbox 与 Action terminal state 在同一 transaction 写入。

## D2-05 Codex 独立设计提案

### 1. 新增 schema v5 的 Run budget ledger

新增 `run_budget_ledger` 表，作为 Run 级预算事实来源：

- `run_id`：每个 Run 唯一；
- `limits_json`：从 `runs.snapshot_json.budget` 冻结拷贝；
- `usage_json`：累计 actual usage；
- `started_actions`：已启动 Action 数；
- `running_actions`：当前 running Action 数；
- `exhausted`：是否已触发预算耗尽；
- `exhausted_reason`：结构化 reason，例如 `max_actions_exhausted`、`wall_clock_exhausted`、`output_bytes_exhausted`、`model_tokens_exhausted`、`cost_exhausted`；
- `exhausted_at`；
- `updated_at`。

不把累计 budget 塞进 `runs.result_json`，避免把终态结果和运行账本混在一起。

### 2. 新增 BudgetAccountingService

服务职责：

- 从 persisted `runs.snapshot_json.budget` 初始化 ledger；
- 在 scheduler claim transaction 内调用 `reserve_action_start(...)`：
  - 检查 Run 未 exhausted；
  - 检查 `started_actions < max_actions`；
  - 检查 `running_actions < max_concurrency`；
  - 递增 started/running；
  - 若达到阈值，阻止 claim，并把 Run 转为 `budget_exceeded`，追加 `run.budget_exceeded`；
- 在 executor completion transaction 内调用 `record_action_usage(...)`：
  - 从 `ActionReceipt.resource_usage` 或 fail-closed estimator 写累计；
  - running_actions 递减；
  - failed / timed_out / effect_unknown 的 usage 也必须入账；
  - 若累计达到或超过 limit，追加 `budget.updated` 与 `budget.threshold_reached`，并阻止后续新 Action。

### 3. scheduler 与 executor 接入点

- Scheduler claim 仍然是唯一启动门，不新增快捷授权路径。
- `RunSchedulerService.claim_action(...)` 在更新 Action 到 running 前执行 budget reserve。
- `LockedUnittestExecutorService._record_completion(...)` 在 receipt 插入后、commit 前执行 usage accounting。
- 所有 budget 事件与 outbox append 仍在同一 SQLite transaction。

### 4. 边界与非目标

- 不建设 provider billing；
- 不建设 GPU/内存强隔离；
- 不把 budget metering 伪装成 OS sandbox；
- 不新增 HTTP mutation route；
- 不让 Action 自报 budget 覆盖 Run snapshot / receipt usage；
- 不绕过 D2-00 authorization、D2-03 admission 或 D2-04 executor。

## 需要 Claude 审查的问题

请逐项给出 `ACCEPT`、`VETO` 或 `尚未达成共识`：

1. D2-05 是否应新增 v5 `run_budget_ledger`，而不是把累计字段放入 `runs.result_json`？
2. `reserve_action_start(...)` 放在 scheduler claim transaction 内，是否足以防止 concurrent claim race 下预算超发？
3. `record_action_usage(...)` 放在 executor completion transaction 内，是否足以保证 failed / timed_out / effect_unknown 的 usage 不丢失？
4. budget exhaustion 是否应沿用 Run terminal state `budget_exceeded` 与事件 `run.budget_exceeded`，并补充 `budget.updated` / `budget.threshold_reached` 作为审计事件？
5. `max_actions` 与 `max_concurrency` 是否应作为 start reservation 预算，而 wall_clock/output/model/cost 作为 receipt usage 累计预算？
6. 是否存在必须 VETO 的点，尤其是 ledger 初始化、事件去重、并发 claim、executor completion race 或 D3 handoff 语义？
