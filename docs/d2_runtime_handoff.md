# Nana D2RuntimeHandoff

版本：`v0.3.0-dev-d2-runtime-handoff-3`

本文件固定 D2 交给 D3 的事实来源。D3 可以读取这些事实并投影 UI/API 状态，但不得重新推导授权、不得绕过 D2 直接执行 Action，也不得把前端状态当作事实来源。

## 1. D3 可消费事实源

D3 的事实源是：

- `runs`
- `actions`
- `action_authorizations`（只读审计绑定，不用于 D3 重新推导授权）
- `events`
- `action_receipts`
- `outbox_events`
- `artifacts`
- command idempotency result
- artifact committed/reconciled projection

D3 不消费 PolicyGrant/Approval 来重新推导“是否应授权”；授权结果已经体现在 Action state、authorization ref、Event、Receipt 中。

`action_authorizations` 是 schema v6 引入的 append-only 授权快照。它把完整 `ActionHashMaterial`、action hash、registry contract digest、authorization source/ref 与 `action.authorized` Event ID 固定在一起。D3 可以展示或核验该绑定，但不得修改它，也不得把它当作绕过 D2 admission 的新授权入口。

## 2. Run / Action 状态机

Run terminal states：

- `succeeded`
- `failed`
- `cancelled`
- `timed_out`
- `budget_exceeded`
- `orphaned`

Action terminal states：

- `succeeded`
- `failed`
- `cancelled`
- `timed_out`
- `denied`
- `expired`
- `effect_unknown`

`effect_unknown` 的含义：

> D2 已知或无法排除外部副作用发生，但无法证明最终效果。D3 必须把它渲染为需要审计/人工确认的未知效果，不能渲染为成功。

运行中取消采用两阶段收敛：Run 先进入 `paused` 并记录 `cancel_requested`，停止并结算所有 running Action 后才进入 `cancelled`。`paused/cancel_requested` 表示“正在终止”，不是可恢复的普通暂停；D3 不得在子进程结算前提前显示为已取消完成。若进程树终止无法验证，Run 必须投影为 `orphaned`，Action/Receipt 为 `effect_unknown`。

`orphaned` 不允许继续调度。已启动 Action 仍须先写 Receipt、记录保守 resource usage，并释放该已结算 Action 的 start reservation（`running_actions` 减一）；这不是宣称未知进程已退出，而是避免把已形成 Receipt 的 Action 永久重复占用 scheduler concurrency。Run 进入 quarantine，后续只能由 reconciliation/人工处置。

## 3. Receipt

每个 terminal executed Action 应有一个 ActionReceipt。D3 必须保留并展示：

- `authorization_source`
- `authorization_ref`
- `approved_by` / `approved_at`（仅 one-time Approval）
- `authorized_effects`
- `actual_effects`
- `effect_violation`
- `result`
- `exit_code`
- `resource_usage`
- artifact refs

如果 `actual_effects` 不是 `authorized_effects` 的子集，`effect_violation=true` 且 `result=effect_unknown`。

locked worker 报告的 observed logical roots 是 advisory audit evidence，不是独立安全边界。强制阻断由测试 import 前安装的 runtime audit guard、空环境、固定 argv/schema 与进程 Job 完成；Receipt 不得把 worker 自报内容宣传为 OS 级证明。

## 4. Event replay

Replay 规则：

- `events.id` 是全局 append-only 顺序；
- 同一个 `run_id` 下 `run_seq` 必须从 1 连续递增；
- 同一个 `(aggregate_type, aggregate_id)` 下 `aggregate_version` 必须从 1 连续递增；
- `outbox_events.event_id` 是 Event 发布资格，不允许删除或改写；
- D3 replay 必须按 Event ID 顺序消费。

## 5. Artifact UI projection

D3 的 UI 可用性投影：

- `artifact.committed` with state `available` -> UI `available`
- `artifact.reconciled` with state `available` -> UI `available`

`artifact.reconciled(state=available)` 是恢复路径，不得伪造成普通 `artifact.committed`。

## 6. Command idempotency

D3 mutation command 必须带稳定 command id 与 request hash：

- 同一 command id + 同一 request hash：返回已存结果，不新增 side effect；
- 同一 command id + 不同 request hash：返回 conflict；
- rejected command 的 replay 必须保留绑定错误，不得重新执行。

## 7. Structured errors

D3 必须显示 D2 structured error code，不以本地 UI 文案替代事实。至少保留：

- `E_CAPABILITY_UNREGISTERED`
- `E_POLICY_GRANT_DENIED`
- `E_APPROVAL_DENIED`
- `E_ACTION_NOT_AUTHORIZED`
- `E_ACTION_CANCEL_RACE`
- `E_RUN_BUDGET_INVALID`
- `E_RUN_CONCURRENCY_LIMIT`
- `E_ACTION_AUTHORIZATION_MISSING`
- `E_ACTION_AUTHORIZATION_INVALID`
- `E_ACTION_AUTHORIZATION_MISMATCH`
- `E_ARGS_ARTIFACT_SIZE`
- `E_ARGS_ARTIFACT_BUDGET`

## 8. OpenAPI/runtime app 合流

D2 仍保持 D0 baseline OpenAPI 与 runtime SSE 分离。D3 若要暴露真实 runtime mutation API，必须单独做 OpenAPI/runtime app 合流决策并重新生成 snapshot，不能悄悄混入 D2。

## 9. Workspace lock preflight

D2 不实现 Workspace lock。D3/real mutation serving 前必须完成：

- 可写打开 SQLite 前取得 OS 级 Workspace lock；
- reconciliation 完成后才 ready；
- 第二实例必须 fail closed；
- release lock 晚于 SQLite close；
- 有第二实例测试和 ready-order 测试。

在 Workspace lock 生命周期完成前，D3 只能做只读 UI 或 fixture/replay 驱动测试，不得开放真实 mutation serving。
