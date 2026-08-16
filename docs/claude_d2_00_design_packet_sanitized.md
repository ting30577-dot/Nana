# Nana D2-00 实施设计包（脱敏）

本文件只包含相对文件定位、契约事实、设计选项和测试要求；不含用户目录、凭据、环境变量值、网络标识或原始日志。

## 目标

在不实现 D2 scheduler/真实 Capability process execution 的前提下，封闭 D0/D1 审计发现的安全与兼容性缺口，使后续 D2 只能建立在失败关闭、可迁移、可重放的基础上。

## 当前事实

- schema 版本为 1，唯一迁移是冻结的 `0001_contract_kernel`。
- Capability 相关 DTO 使用 digest 可空的 `VersionedRef`。
- `actions.executable_digest`、`policy_grants.executable_digest` 可空。
- Approval 的 `allowed_uses >= 1`。
- `policy_grant_matches` 直接解释一个小型 JSON Schema 子集；非法嵌套类型可能抛 TypeError。
- 授权 datetime 可混用 naive 与 aware。
- 初始化数据库先设置 WAL，后检查 schema ceiling。
- Event/canonical state/outbox 当前写入使用同一 `BEGIN IMMEDIATE` 事务。
- outbox 已有 `dispatched_at`、`attempts`，SSE replay 使用 Event 与 outbox INNER JOIN。
- 尚无可执行的 Capability Registry。
- ActionReceipt 只有 `actual_effects`，没有 `authorized_effects` 和越界标记。

## Codex 独立实施提案

### 1. 契约身份与 Registry

- 保留通用 `VersionedRef` 给非执行引用。
- 新增 digest 必填的 `CapabilityRef`，Action、Approval、PolicyGrant、相关 Command 和 ActionHashMaterial 全部改用。
- 新增闭合 `CapabilityRegistryEntry`：
  - CapabilityRef；
  - 安全 args schema；
  - 固定 risk tier、reversible；
  - authorization mode；
  - grantable；
  - provider mode 与 provider allowlist；
  - registry contract digest。
- entry 构造时重算 contract digest；授权判定必须接收 Registry entry，校验 ref、risk、reversible、provider 和 args，不能信任 Action 自报。
- 三个绝对不可 Grant 的 capability 在判定器中独立硬拒绝，并要求 Registry 也声明不可 Grant。

### 2. 策略与时间

- 把安全 JSON Schema 子集的“元校验”和“值匹配”拆到独立模块。
- CapabilityConstraints 与 Registry entry 创建时递归元校验。
- 匹配器对任何异常返回明确失败原因，不向外抛解释器异常。
- 授权相关时间使用统一 `UTCDateTime`：拒绝 naive，aware 输入归一化为 UTC。
- Grant provider 约束：非空 allowlist 不允许 `provider=None`；空 allowlist 不允许任意非空 provider。Registry 的 required/optional/forbidden 模式先行约束。

### 3. 一次性 Approval 与 Receipt

- Approval/RequestApproval 的 `allowed_uses` 改为字面量 1。
- migration 0002 对旧数据做 fail-fast guard，并用触发器拒绝未来 digest 空值和 `allowed_uses != 1`。
- 新增 `approval_consumptions`：`approval_id` 为主键、`action_id` 唯一，从持久层保证同一 Approval 只能消费一次。
- ActionReceipt 增加 `authorized_effects` 与 `effect_violation`；若 actual 不是 authorized 子集，必须标记 violation 且结果为 `effect_unknown`，仍保留真实 actual。
- D2 scheduler 后续必须在一个 `BEGIN IMMEDIATE` 事务中完成 Approval 消费、Action authorized 状态与 Event/outbox。

### 4. 数据库与重放

- schema 升至 2，新增 append-only 0002，不修改 0001。
- 对现有非空数据库先用 `mode=ro` 检查 ceiling/history，再打开读写连接；读写连接在 WAL 前再次验证，避免拒绝前持久化副作用。
- 增加公开 `connect_database_readonly`，SSE 改用真只读连接。
- migration 0002 增加：
  - capability registry 表；
  - approval consumption 表；
  - authorized receipt 字段；
  - digest/one-time guard；
  - Event 禁 update/delete；
  - outbox 禁 delete、禁改 event_id，允许更新 dispatched_at/attempts。
- 保持 SQLite 单 writer、数据库分配 Event ID、Event/state/outbox 同事务；增加双连接竞争回归。

### 5. 权威证据与生成物

- 新增外部权威规格的逻辑文件名 + SHA-256 manifest，不把本地同名副本宣称为权威。
- 增加验证脚本，显式接收 authority root；脚本不记录绝对路径。
- 重新生成 OpenAPI 与 TypeScript，加入 diff/类型检查。
- 新增 D2-00 聚焦测试：四个原始反例、Registry 自报不可信、绝对例外、消费唯一性、高 schema 零字节/零 PRAGMA 变化、outbox retention、Event append-only、迁移升级/回滚、只读 SSE、Receipt 越界、UTC。

## 需要 Claude 独立审理的问题

1. 上述设计有无遗漏 D2-00 的已决门槛？
2. Registry `contract_digest` 自校验是否足够作为当前本地闭合注册表的完整性锚？如果不足，在不引入尚未设计的密钥管理系统时，最低可执行替代是什么？
3. 0002 使用 fail-fast guard + triggers，而不重建 v1 大表，是否可接受？请特别审查 SQLite 外键和迁移原子性。
4. Receipt 的 `actual ⊄ authorized => effect_violation=true 且 result=effect_unknown` 是否过强或正确？
5. 只读预检后再读写打开存在 TOCTOU；在当前单 Workspace owner/未来 Workspace lock 前提下是否可接受？
6. 请按 ACCEPT、VETO、未达成共识逐项裁定，并给出必须修改的最小集合。
