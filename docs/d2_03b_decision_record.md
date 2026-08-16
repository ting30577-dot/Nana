# Nana D2-03b 决策记录

## 最终复审修正

Codex 最终扫描发现 admission 仍信任调用方提供的 `current_concurrency` 与 `projected_cumulative_budget`，且完整 ActionHashMaterial 没有持久化。修复后：

- schema v6 `action_authorizations` append-only 保存完整 material、action hash、registry contract digest、source/ref 与授权 Event ID；
- PolicyGrant 并发与累计预算由数据库内 Action state 和既有 authorization material 原子派生；调用方 context 只保留 project binding，不再是预算事实源；
- 测试证明伪造低累计值不能绕过 grant cumulative budget，且 authorization row 不可更新或删除。

Codex：ACCEPT。Claude 最终首轮对 F3 明确 ACCEPT：`BEGIN IMMEDIATE` 内从持久事实派生 cumulative budget/uses/concurrency，调用方不能伪造低使用量。

## 阶段目标

D2-03b 的目标是实现 Capability admission service：把 D2-00 授权函数、D2-01 scheduler claim 前置条件、D2-03a 持久化 registry truth 串成原子授权准入闭环。

本阶段不实现 executor、unittest 运行、stdout/stderr artifact、ActionReceipt、HTTP mutation route、OpenAPI/runtime app 合流或 D3 UI。

## 逐项扫描结果

| 扫描项 | 发现 | 处理 |
|---|---|---|
| 持久化 registry truth | D2-03a 已提供完整 `entry_json + contract_digest`，可供 admission 查询。 | 复用现有 schema v4，不新增迁移。 |
| args artifact 绑定 | `actions` 表只存 args artifact id/hash；D2-03b 需要从 artifact 字节重建 canonical args。 | `CapabilityAdmissionService` 通过注入的 args artifact loader 读取字节、校验 artifact blob hash、重算 canonical args hash，并与 Action/Material 反证。 |
| ActionHashMaterial 来源 | 当前 `AuthorizeAction` command envelope 不包含 provider、budget、network_methods、reversible 等完整授权材料。 | service 接收完整 `ActionHashMaterial`，再用持久化 action / registry / artifact / grant / approval 反证绑定；Claude 最终 F3/F11 ACCEPT。 |
| PolicyGrant 路径 | 没有原子 consumption。 | 新增 policy grant admission：`policy_grant_matches(...)` 通过后，同一事务写 Action authorized、event/outbox、grant `uses += 1`，末次使用转 `exhausted`。 |
| Approval 路径 | `approval_consumptions` 表存在，但没有写入路径。 | 新增 approval admission：`approval_authorizes(...)` 通过后，同一事务写 Action authorized、event/outbox、`approval_consumptions`。 |
| replay / race | 原先无 admission 服务，因此无法证明同一 action 或 approval 只授权一次。 | 新增测试覆盖 action 二次授权失败、已有 approval consumption fail-closed。 |
| rollback | 需要证明 event/outbox/consumption/state 在同一事务。 | 新增 outbox fault injection 测试，确认 action、event、grant use 全部回滚。 |
| scheduler 边界 | scheduler 只能 claim `authorized` action。 | admission service 只把 Action 推到 `authorized`，不 claim、不执行。 |
| Claude 协作 | 早期调用曾连接失败/超时。 | 服务恢复后的最终复审确认 F3/F11 与 D2-07 ACCEPT，历史未共识状态已收敛。 |

## 决策表

| 决策 | Codex 结论 | Claude 结论 | 当前状态 | 证据 |
|---|---|---|---|---|
| 新增 `CapabilityAdmissionService`，不混入 executor/Receipt/API | ACCEPT | ACCEPT | ACCEPT | `nana_sidecar.storage.admission`；focused tests 通过。 |
| service 接收完整 `ActionHashMaterial` 并反证持久化绑定 | ACCEPT | ACCEPT | ACCEPT | 测试覆盖 args/action hash/material/registry 绑定。 |
| PolicyGrant consumption 用 `uses += 1`，末次使用转 `exhausted` | ACCEPT | ACCEPT | ACCEPT | `test_policy_grant_last_use_marks_grant_exhausted`。 |
| Approval consumption 写入 `approval_consumptions`，拒绝 replay | ACCEPT | ACCEPT | ACCEPT | one-time consumption/replay tests。 |
| `action.authorized` event 最小 payload 记录 source/ref/effects/state | ACCEPT | ACCEPT | ACCEPT | authorization Event/material binding tests。 |

## 已知未决项

- 无 D2-03b blocker。公开 mutation command envelope 与 runtime app 合流属于 D3；D2 service/durable snapshot 已保存完整 material。

## 验证记录

- `python -m unittest tests.test_d2_capability_admission -v`：8 tests OK。
- `python -m unittest tests.test_d2_capability_admission tests.test_d2_run_scheduler tests.test_vnext_storage tests.test_vnext_contracts -v`：71 tests OK。
