# Nana D2-00 实施摘要（脱敏）

目标：将 D0/D1 审计发现的 D2-00 缺口封闭在契约层、授权层、存储迁移层、SSE 读取层和隐私定位符层；不实现 D2 scheduler 或真实执行器。

已完成的实现要点：

- 新增 `CapabilityRef`，用于可执行能力，`digest` 为必填。
- 新增 `CapabilityRegistryEntry`、`CapabilityAuthorizationMode`、`CapabilityProviderMode`。
- `approval_authorizes` 与 `policy_grant_matches` 现在都要求 Registry entry 参与判定。
- 安全 JSON-Schema 子集已拆出独立校验模块，非法嵌套 schema 失败关闭，不再泄漏 TypeError。
- `Approval.allowed_uses` 与 `RequestApproval.allowed_uses` 已收敛为字面量 1。
- `PolicyGrant.created_at`、`CapabilityConstraints.valid_from/expires_at`、`Approval.expires_at/decided_at`、`RequestApproval.expires_at` 等授权时间统一拒绝 naive datetime 并归一化为 UTC aware。
- `ActionReceipt` 新增 `authorized_effects` 与 `effect_violation`，并校验越界时必须是 `effect_unknown`。
- `Resource.logical_ref`、`WebCoordinates`、`RepoCoordinates` 已加隐私/凭据约束。
- SQLite schema 升到 v2，加入：
  - `capability_registry_entries`
  - `approval_consumptions`
  - `action_receipts` 新列
  - actions / policy_grants / approvals 的 fail-closed 触发器
  - events append-only 触发器
  - outbox retain-only 触发器
- `initialize_database` 先做只读预检，避免高版本库在拒绝前产生写副作用。
- 新增 `connect_database_readonly`，SSE 使用真只读连接。
- `LocalSession.token` 的 `repr` 已隐藏。
- OpenAPI 生成脚本仍以 D0 `create_app()` 为源，保持当前 `openapi.json`/TS 生成链与现有测试一致。

验证结果：

- `python -m compileall nana_sidecar tests scripts` 通过
- `python -m unittest` 通过，206 tests

请独立审查：

1. 这些 D2-00 加固是否存在遗漏或过强限制；
2. Registry digest 与 one-time approval / grantable 约束是否足够；
3. 只读预检 + WAL 初始化是否还有未覆盖的迁移风险；
4. `approval_authorizes` / `policy_grant_matches` 的最小调用约束是否可接受。
