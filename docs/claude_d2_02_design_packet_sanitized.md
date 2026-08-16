# Nana D2-02 设计包（脱敏）

本文件仅包含相对文件/模块名、契约事实、本地测试结果和设计问题；不包含用户名、
绝对路径、token、网络标识、凭据、环境变量值或原始日志。

## 当前事实

- D0 contract kernel 已完成。
- D1 Artifact/Event runtime 与 HTTP SSE 已完成。
- D2-00 已完成 authorization/storage hardening：
  - `CapabilityRef` 必须包含 id/version/digest；
  - `CapabilityRegistryEntry` 已存在；
  - `approval_authorizes(...)` 与 `policy_grant_matches(...)` 必须接收 registry entry；
  - Safe JSON Schema 子集已独立实现；
  - one-time Approval 的 `allowed_uses` 固定为 1；
  - storage schema v2 加入 `capability_registry_entries`、`approval_consumptions`、
    append-only events、retain-only outbox、readonly preflight/connection 等保护。
- D2-01 已完成 scheduler admission/cancel gate：
  - 新增 `RunSchedulerService`；
  - claim 已 authorized Action 时写 `action.started`；
  - Run cancel 会写 `run.cancelled`、pending Action 写 `action.cancelled`、
    claimed/running Action 写 `action.effect_unknown`；
  - `max_actions` 只作为 scheduler count gate；
  - schema version/read ceiling 已提升到 3。
- 当前基线：
  - `python -m compileall nana_sidecar tests scripts` 通过；
  - `python -m unittest discover -s tests -v` 通过 `213/213`；
  - 仍有既有旧 UI shutdown `gc` ResourceWarning，不阻塞 D2。

## 权威依据

- `11_首个纵向切片执行清单.md` 在 D1 之后排序为：
  `scheduler/cancel` → `capability/policy/budget` → React UI → dev fixture。
- Workstream 3 的 DoD 包含：
  - Agent 无法调用未注册工具；
  - 参数/路径越界在执行前被拒；
  - 取消停止新 Action；
  - 预算达到 100% 不再启动动作；
  - 锁定安全语料中未批准的 T3/T4 动作为零；
  - Grant 只覆盖满足 capability/参数/目录/网络/预算/期限约束的 Action。
- ADR-005 指定首个 dev capability：
  `python.unittest.locked`，只允许 fixture 中冻结的 test identifiers，network denied，
  writes restricted to project scratch，并在 scheduler/cancel foundations 之后实现。
- ADR-007 要求 path/network/environment/process-tree/timeout/budget fixtures 在自动执行前
  证明 zero unblocked violations；`builtin_local` 不是强 sandbox，unknown code 不能
  无审批自动运行。

## Codex 独立 D2-02 提案

Codex 提议 D2-02 的正式目标是：

> 建立第一个注册 capability 的 policy admission gate，而不是执行器。

D2-02 应实现 `python.unittest.locked` 的注册/查询与 Action 授权准入闭环，使后续
D2 执行器只能启动已经被 D2-02 授权、并继续能被 D2-01 scheduler claim 的 Action。

### 建议范围

1. 增加一个 storage/runtime service，例如 `CapabilityPolicyService`。
2. 增加内置 registry bootstrap/query：
   - 注册 `python.unittest.locked`；
   - capability id/version/digest 固定；
   - args schema 只允许 fixture 中冻结的 test identifier；
   - network denied；
   - provider forbidden；
   - risk tier 保持低风险但不可由 Action 自报覆盖。
3. 从 Action 的 `args_artifact_id` 读取 canonical JSON args，重新计算 `args_hash`，
   构造 `ActionHashMaterial`。
4. 使用 registry entry + `policy_grant_matches(...)` 或 `approval_authorizes(...)`
   做唯一授权路径：
   - PolicyGrant 成功：Action `proposed` → `authorized`，写 `action.authorized`
     Event/outbox，并记录 `authorization_ref`；
   - Approval 成功：同上，并在同一事务写 `approval_consumptions`，保证一次性；
   - 不匹配或需要审批：不得授权，不得进入 scheduler claim；
   - T4/never-grant capability 不允许 PolicyGrant 授权。
5. D2-02 可以实现“policy admission”层的 budget/context 检查，例如：
   - `policy_grant_matches` 的 per-action/cumulative budget；
   - grant uses/max_uses；
   - current_concurrency；
   - 但不实现真实资源消耗计量，不产生 Receipt。
6. 为 `python.unittest.locked` 增加锁定安全语料：
   - 未注册 capability 拒绝；
   - capability digest 不匹配拒绝；
   - test identifier 不在 fixture 白名单拒绝；
   - network/write/process scope 越界拒绝；
   - T3/T4 或 `NEVER_GRANT_CAPABILITY_IDS` 不能被 Grant 授权；
   - Approval replay 被 `approval_consumptions` 拒绝。

### 明确不做

- 不 spawn child process；
- 不运行 unittest；
- 不读取环境变量或传递子进程 env；
- 不写 stdout/stderr Artifact；
- 不生成 ActionReceipt；
- 不实现 T3 export fixture；
- 不新增 HTTP mutation route；
- 不做 React UI；
- 不做 Tauri/launcher/workspace-lock；
- 不把 OpenAPI/runtime app 合流偷偷混入本单元。

## 需要 Claude 审查的问题

请独立审查并用紧凑表格给出 `ACCEPT`、`VETO` 或 `未达成共识`。

1. D2-02 是否应定义为 `python.unittest.locked` 的 registered capability + policy
   admission gate，而不是直接进入真实 process execution？
2. D2-02 是否应该在此时实现 Approval consumption transaction，还是应先只做
   PolicyGrant 授权，Approval 留到 T3/T4 fixture 前？
3. `CapabilityRegistryEntry` 当前字段是否足够承载 `python.unittest.locked` 的
   path/network/env/process/resource 限制？如果不足，最低可接受的契约扩展是什么？
4. D2-02 的 budget 范围是否应仅限 admission context（per-action/cumulative/max_uses/
   concurrency），把真实资源计量和 Receipt 留给执行器单元？
5. Codex 编码前的最小必备测试集是什么？

如 VETO 任一项，请给出使设计可接受的最小具体修改。
