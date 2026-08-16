# Nana D2-03a 实施摘要（脱敏）

本文件仅包含相对模块名、契约事实和本地测试结果；不包含用户名、绝对路径、token、环境变量值、内网地址、设备序列号、软件授权、日志凭据或未脱敏诊断信息。

## 背景

D2-02 后发现三个阻塞：

1. `CapabilityRegistryEntry` 已包含 read/write/network/env/process/timeout/default-effect ceiling，但 SQLite `capability_registry_entries` 只保存基础字段，无法持久化完整 registry truth。
2. `python.unittest.locked` 是 `POLICY_GRANT` 且 `grantable=True`，registry ceiling 允许 `builtin:python.unittest.locked` process target，但 `policy_grant_matches(...)` 对任何 process effect 一律 `process_scope_not_grantable`。
3. `python.unittest.locked` 的 `read_roots=()`，但 locked unittest 后续需要读取项目源码和测试文件。

## 已实施

- schema version/read ceiling 从 3 升级到 4。
- 新增 migration `0004_d2_03a_full_capability_registry`。
- `capability_registry_entries` 改为保存：
  - `capability_id`
  - `capability_version`
  - `executable_digest`
  - `entry_json`
  - `contract_digest`
  - `created_at`
- `entry_json` 必须是完整 `CapabilityRegistryEntry` JSON；表级 CHECK 验证 capability id/version/digest、contract digest，以及 read/write/network/env/process/default-effect 字段存在。
- v3 旧 registry 表如果已有 rows，v4 migration 失败关闭，因为旧 rows 无法无损重建 execution ceiling。
- `CapabilityConstraints` 增加 `process_targets`。
- `policy_grant_matches(...)` 对 `material.requested_effects.processes` 做 subset-of `constraints.process_targets` 检查；不再一律拒绝所有 process effect。
- `python.unittest.locked` registry entry 的 `read_roots` 改为 `("project:source", "project:tests")`，并保留 fixed process target `("builtin:python.unittest.locked",)`。
- OpenAPI snapshot 与 TypeScript client 已重新生成。

## 已验证

- `python -m compileall nana_sidecar tests scripts`：通过。
- `python -m unittest tests.test_vnext_contracts tests.test_vnext_storage tests.test_vnext_sidecar -v`：功能性通过；manifest 更新前仅剩 hash mismatch。

## 请求 Claude 审查

请独立审查并给出 `ACCEPT`、`VETO` 或 `尚未达成共识`：

1. 用 canonical full registry `entry_json + contract_digest` 替代基础字段表，是否足以解除 D2-03b “从持久化 registry 读取完整 Capability 真相”的阻塞？
2. v3 旧 registry rows 无法安全升级时失败关闭，是否正确？
3. `CapabilityConstraints.process_targets` + `policy_grant_matches` 精确 subset 语义，是否解决 `python.unittest.locked` process 授权矛盾？
4. `python.unittest.locked` 的 canonical read scope 使用 `project:source` 与 `project:tests` 是否足够作为 D2-04 runtime enforcement 前置契约？
5. 是否还有必须先修的 D2-03a 阻塞，才能进入 D2-03b admission service？

