# Nana D2-03b 设计包（脱敏）

目标：把 D2-03a 之后的 Capability admission service 落到持久化事务层，串起 registry truth、args artifact、PolicyGrant / Approval、Action authorized、Event/outbox 与消费记录。

当前已确定事实：
- D2-03a 已完成；
- `capability_registry_entries` 现在保存 canonical full registry `entry_json + contract_digest`；
- `CapabilityConstraints.process_targets` 已存在；
- `policy_grant_matches(...)` 已支持 process 精确 subset；
- `python.unittest.locked` 的 read scope 已固定为 `project:source` 与 `project:tests`；
- schema 中已存在 `policy_grants`、`approvals`、`approval_consumptions`、`actions`、`events`、`outbox_events`；
- 目前还没有 admission service；
- `nana_sidecar/storage/run_scheduler.py` 只负责 D2-01 claim/cancel，不负责授权；
- 当前 `AuthorizeAction` 命令 envelope 只含 `action_id`、`action_hash`、`authorization_ref`，没有完整 `ActionHashMaterial`。

Codex 当前独立提案：
- 新增 `nana_sidecar.storage.admission`，实现一个 `CapabilityAdmissionService`；
- 该服务只做持久化 admission，不做 executor、Receipt 或 HTTP mutation route；
- 其核心方法面向两条路径：
  - policy grant hit：同一 SQLite 事务内完成 grant 读取、`policy_grant_matches(...)`、grant uses 增量/耗尽、`actions` 置为 authorized、`action.authorized` event、outbox append；
  - approval hit：同一 SQLite 事务内完成 approval 读取、`approval_authorizes(...)`、`approval_consumptions` 插入、`actions` 置为 authorized、`action.authorized` event、outbox append；
- 为了验证 registry / args artifact 绑定，service 需要读取 action 关联的 args artifact 并重建 canonical args JSON；
- Codex 目前倾向让 admission service 直接接收完整 `ActionHashMaterial`，再用持久化 action / registry / grant / approval / args artifact 反证它；否则现有 `AuthorizeAction` envelope 不足以独立表达 budget、provider、reversible、network_methods 等授权材料。

需要 Claude 独立审查并返回 `ACCEPT` / `VETO` / `尚未达成共识`：
1. admission service 以完整 `ActionHashMaterial` 为输入、再用持久化数据反证绑定，这个边界是否可接受？
2. 是否应现在就扩展 `AuthorizeAction` command envelope，而不是先让 service 直接吃完整 material？
3. policy grant 的 consumption 采用 `uses += 1` 并在到达上限时转为 exhausted，这个模型是否足够？
4. approval 路径把 `approval_consumptions` 作为一次性消费账本，这个事务边界是否正确？
5. `action.authorized` event 的最小审计字段是否应包含 authorization source / ref / previous_state / state / action_id？
6. 以上方案是否会误伤 D2-04 locked executor、D2-05 budget/runtime、或 D3 handoff contract？
