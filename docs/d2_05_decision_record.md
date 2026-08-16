# Nana D2-05 决策记录

## 最终复审修正

补充回归覆盖 runner exception、running cancel 与 `orphaned`：三条路径都在 completion transaction 中写 Receipt、调用 `record_action_usage(...)` 并把已结算 Action 的 `running_actions` reservation 减回 0；orphaned Run 随后 quarantine，不再调度。Claude 二审 F1/F5 ACCEPT；D2-05 最终共同 ACCEPT。

## 阶段目标

D2-05 把 D2-01 的 count gate 与 D2-03 admission budget context 扩展为真实 runtime budget accounting，使 Action start reservation 与 executor receipt usage 都能被 Run 级账本追溯。

本阶段不建设 provider billing、GPU/内存强隔离、通用 sandbox、HTTP mutation route、D3 UI、OpenAPI/runtime app 合流或外部 publish/export。

## 逐项扫描结果

| 扫描项 | 发现 | 处理 |
|---|---|---|
| D2-01 scheduler | 已有 `max_actions` count gate，但没有 Run 级累计 usage ledger。 | 拟新增 v5 `run_budget_ledger`，并把 claim start reservation 接入 scheduler。 |
| D2-03 admission | 已检查 per-action / cumulative budget context，但不做真实 resource accounting。 | 保持 admission 不执行、不落 usage；D2-05 消费 receipt usage。 |
| D2-04 executor | 已写 `ActionReceipt.resource_usage`，但不会累计到 Run budget。 | 拟在 completion transaction 内记录 usage。 |
| 事件类型 | schema 已包含 `run.budget_exceeded`、`budget.updated`、`budget.threshold_reached`。 | 拟复用已有事件类型，不新增 HTTP contract。 |
| 并发超发 | scheduler 使用 `BEGIN IMMEDIATE`，适合在同一 transaction 内做 reserve。 | 拟把 budget reserve 放在 Action update to running 之前。 |
| failed/effect_unknown usage | receipt 已能记录失败与未知结果 usage。 | 拟要求所有 terminal receipt 都入账。 |

## 决策表

| 决策 | Codex 结论 | Claude 结论 | 当前状态 | 证据 |
|---|---|---|---|---|
| 新增 v5 `run_budget_ledger` 作为 Run budget truth | ACCEPT | 二审 ACCEPT（F1/F5） | ACCEPT | D2-05 需要可重放累计 usage，现有 schema 无 ledger。 |
| scheduler claim 前做 `reserve_action_start` | ACCEPT | 二审 ACCEPT（F1/F5） | ACCEPT | `BEGIN IMMEDIATE` 可压住 concurrent claim race。 |
| executor completion 事务内做 `record_action_usage` | ACCEPT | 二审 ACCEPT（F1/F5） | ACCEPT | D2-04 receipt 与 terminal event 已同事务写入。 |
| budget exhaustion 沿用 `run.budget_exceeded`，并补充 budget audit events | ACCEPT | 二审 ACCEPT（F1/F5） | ACCEPT | 事件 enum 已存在。 |
| 不把 budget 当 OS sandbox 或 billing 系统 | ACCEPT | 二审 ACCEPT（范围确认） | ACCEPT | D2-05 非目标。 |

## 待验证退出证据

- budget under limit 可执行：已覆盖；
- budget exactly/exceeds limit 阻止新 Action：已覆盖；
- concurrent claim race 下不会超发：已覆盖；
- failed / timed_out / effect_unknown Action 的 resource accounting 不丢失：已覆盖。

## 验证记录

- `python -m unittest tests.test_d2_budget_accounting tests.test_d2_capability_admission tests.test_d2_run_scheduler tests.test_d2_locked_executor tests.test_vnext_contracts tests.test_vnext_storage tests.test_vnext_sidecar -v`：87 tests OK。
- `python -m compileall nana_sidecar tests scripts`：OK。
- `python -m unittest discover -s tests -v`：238 tests OK；结尾存在既有 `gc ResourceWarning`，退出码为 0。
- `npm run check`：OK。

## Claude 状态

- 2026-07-31：调用 `scripts/ask_claude.py` 审查 `docs/claude_d2_05_design_packet_sanitized.md`，返回“无法连接 Claude 服务，请检查网络和 NANA_CLAUDE_BASE_URL”。
- `python -m unittest tests.test_claude_reviewer -v`：6 tests OK。
- 上述为历史调用故障；服务恢复后 Claude 二审 F1/F5 ACCEPT，D2-05 已共同收敛。
