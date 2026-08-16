# Nana D2-01 决策记录

## 最终复审修正

D2-04 已引入真实子进程后，Codex VETO 了“cancel 立即把 running Action 写为 `effect_unknown`”的旧语义。最终语义为：Run 先进入 `paused/cancel_requested`，pending Action 仍直接 `cancelled`，running Action 保持 `running` 直到 executor 完成进程树终止、Receipt 和预算结算；之后 Action 为 `effect_unknown`，Run 为 `cancelled`。若终止无法验证，Run 为 `orphaned`。handoff v3 已明确终止中投影与 orphaned usage/reservation；Claude 二审 F1 ACCEPT，最终共同 ACCEPT。

本记录已脱敏，只使用相对模块名、本地命令摘要和设计结论。

## 基线

- `python -m compileall nana_sidecar tests scripts`：D2-01 修改前通过。
- `python -m unittest discover -s tests -v`：D2-01 修改前 `206/206` 通过。
- 保留已有 dirty worktree。未授权 reset、checkout、clean 或删除无关文件。

## 决策

| 决策 | Codex 结论 | Claude 结论 | 状态 | 证据与处理 |
|---|---|---|---|---|
| D2-01 目标 | 持久化 scheduler admission 加 cancel/budget gate，暂不做真实工具/进程执行。 | ACCEPT。 | ACCEPT | `07` 将 D2 定义为 process/action/policy/budget；`11` 将 scheduler/cancel 排在 capability/policy/budget 前；`12` 明确 D2-00 没有实现 scheduler 或 execution。 |
| D2-01 中的 `max_actions` | 只作为 scheduler 计数准入门。不要实现 cost、token、wall-clock、model、policy 或 grant budget consumption。 | 初始为 `未达成共识`；若收窄为纯计数 gate 则 ACCEPT。 | ACCEPT | Codex 接受该收窄条件。因此 `max_actions` 是 stop-the-line scheduler guard，不是后续 budget runtime。 |
| Run cancel 对 pending Actions 的处理 | Pending Actions 应转为 `cancelled` 并发出专用事件。 | VETO 复用 `action.completed`；要求新增 `action.cancelled`。 | ACCEPT | Codex 接受该 VETO。D2-01 会新增 `action.cancelled`，而不是重载 completion 语义。 |
| Run cancel 对 claimed/running Actions 的处理 | Claimed/running Actions 转为 `effect_unknown` 并发出 `action.effect_unknown`。不声称已 kill process。 | ACCEPT。 | ACCEPT | 当 Action 已被 claim 但 D2-01 没有 process executor 证据时，这保留了审计诚实性。 |
| D2-01 non-goals | 不做任意 shell、child process spawn、unknown code execution、HTTP mutation route、approval/grant consumption、external export、React、Tauri 或 alpha.1 内容。 | ACCEPT。 | ACCEPT | 这些 non-goals 在建立 scheduler state gate 的同时，保护 D1 与 D2-00 安全边界。 |
| 最小测试 | 增加 claim race、invalid claim、count gate、cancel pending/running actions、cancel idempotency、claim/cancel race、event/outbox invariants，以及 cancel 路径不得出现 `action.completed`。 | ACCEPT，并要求新增 `action.cancelled`。 | ACCEPT | 测试设计覆盖 transactionality、event/outbox append、run_seq monotonicity，以及 cancel 后 no-later-claim。 |

## 剩余明确未达成共识项

- `action.effect_unknown` 是否应携带额外的未来导向标记，例如“已 claim 但未观测到
  output”，仍未解决。D2-01 使用最小 reason payload，且不声称 process-executor 证据。

## 实现范围

D2-01 可以新增 scheduler service 和新的 `action.cancelled` event type。不得实现真实
执行、process-tree cancellation、approval consumption、policy grant consumption、
external export、React UI、Tauri 或 launcher/workspace-lock 行为。
