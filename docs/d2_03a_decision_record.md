# Nana D2-03a 决策记录

本记录已脱敏，只使用相对模块名、本地命令摘要和设计结论。

## 背景

D2-02 后存在三个阻塞：

1. `CapabilityRegistryEntry` 契约已包含 execution ceiling，但 SQLite `capability_registry_entries` 仍只保存基础字段。
2. `python.unittest.locked` 声明 process target，但 `policy_grant_matches(...)` 对所有 process effect 一律拒绝。
3. `python.unittest.locked` 的 `read_roots=()` 与真实 unittest 需要读取源码/测试文件冲突。

Claude 最终对 F10 明确 ACCEPT：canonical full `entry_json` + contract digest + fail-closed migration 足以重建完整 registry truth；pinned digest 与 v4→v6 round-trip 已共同收敛。

## 决策

| 决策 | Codex 结论 | 状态 | 证据与处理 |
|---|---|---|---|
| Registry 持久化形式 | 使用 canonical full registry `entry_json` + `contract_digest`，不把每个 ceiling 字段拆成列。 | ACCEPT | 这样 D2-03b 可从持久化 registry 重建完整 Capability truth，后续字段扩展也不需要继续拆表。 |
| v3 旧 registry row 迁移 | 旧表若已有 rows，v4 migration 失败关闭。 | ACCEPT | 旧 row 没有 execution ceiling，无法安全重建完整 truth；测试覆盖 `v3_upgrade_refuses_incomplete_registry_rows`。 |
| process grant 语义 | `CapabilityConstraints` 增加 `process_targets`，`policy_grant_matches(...)` 对 process effect 做精确 subset 检查。 | ACCEPT | 不放开所有 process，也不隐藏 process effect；合法 locked unittest 必须声明固定 process target。 |
| locked unittest read scope | 固定为 `project:source` 与 `project:tests`。 | ACCEPT | 这些 roots 进入 registry ceiling、Action requested effects、Grant constraints 与未来 executor runtime enforcement。 |

补充边界：这里的 read scope 只约束项目拥有的源码/测试树；`python` 解释器、stdlib、site-packages 与运行时 import 解析路径属于 D2-04 executor/resolver 职责，不应写进 registry truth。

## 实现范围

- schema version/read ceiling 升级到 4；
- migration `0004_d2_03a_full_capability_registry`；
- `CapabilityConstraints.process_targets`；
- `policy_grant_matches(...)` process scope 匹配；
- `python_unittest_locked_registry_entry()` read scope 修正；
- OpenAPI/TS snapshot 重新生成；
- storage/contract tests 更新。

## 明确不做

- 不实现 admission service；
- 不消费 Approval；
- 不消费 PolicyGrant uses；
- 不运行 unittest；
- 不写 ActionReceipt；
- 不开放 runtime mutation route。

## Claude 复核与收敛

Claude 对 D2-03a 的方向给出条件性审查：

| 议题 | Claude 结论 | Codex 处理 | 状态 |
|---|---|---|---|
| full registry `entry_json + contract_digest` | 尚未达成共识，缺 round-trip 与列/JSON 一致性证据。 | 新增 contract round-trip 与 storage round-trip 测试；验证 `executable_digest`、`contract_digest` 列与 `entry_json` 内重建的 `CapabilityRegistryEntry` 一致。 | ACCEPT |
| v3 旧 registry rows 失败关闭 | ACCEPT with condition。 | 保留 v4 migration 对已有 v3 registry rows fail closed；补救路径是清空/重建不完整 registry 后再迁移。 | ACCEPT |
| process targets subset 语义 | ACCEPT with condition。 | 保持 `constraints.process_targets ⊆ registry_entry.process_targets` 的授权检查，并在 locked unittest 测试中断言 Grant constraints 与 registry ceiling 使用同一固定 process target。 | ACCEPT |
| locked unittest read scope | 尚未达成共识，需澄清 import 解析路径。 | 固定 `project:source` 与 `project:tests` 为项目可读根；解释器、stdlib、site-packages 与 import resolver 留给 D2-04 executor/resolver，不写入 registry truth。 | ACCEPT for D2-03a，D2-04 继续设计 |
