# Nana D2-02 决策记录

## 最终复审修正

- `CapabilityConstraints.process_targets` 已在 D2-03a 加入，PolicyGrant 对 process effect 使用精确 subset 语义；旧的“所有 process fail closed”临时策略已被替代。
- `python.unittest.locked` 会启动固定子进程，因此风险等级从 T1 修正为 T2。
- 合法 Action 的最小 requested effects 为 `project:source`、`project:tests` 与固定 process target；不声明未使用的 scratch write。
- Claude 最终首轮对 F9（T2/minimum privilege）明确 ACCEPT；frozen capability 无写权限、固定 process target 与 read roots 的结论已共同收敛。

本记录已脱敏，只使用相对模块名、本地命令摘要和设计结论。

## 基线

- D2-01 已完成，当前 schema/read ceiling 为 3。
- D2-01 基线验证曾通过 `python -m compileall nana_sidecar tests scripts` 与完整 unittest。
- 本阶段开始前已重新阅读协作说明、权威规格摘录、D2-00/D2-01 状态，并保留已有 dirty worktree。未 reset、checkout、clean 或删除无关文件。

## 决策

| 决策 | Codex 结论 | Claude 结论 | 状态 | 证据与处理 |
|---|---|---|---|---|
| D2-02 正式目标 | 先做 `python.unittest.locked` 的 capability registry ceiling 与 admission 前置契约，不进入真实进程执行。 | ACCEPT：D2-02 可定义为 registered capability + policy admission gate，而不是 executor。 | ACCEPT | ADR-005 要求首个 dev capability 是 `python.unittest.locked`；ADR-007 要求自动执行前先证明 path/network/env/process/timeout/budget gate。 |
| Registry entry 是否需要 execution envelope ceiling | D2-00 的 `CapabilityRegistryEntry` 还不足以表达 capability 自身的网络、文件、环境、进程、timeout 上限；必须先扩展 registry。 | conditional ACCEPT：在 admission 前加入 capability-level ceiling，grant 只能收窄不能放宽。 | ACCEPT | 已在 `CapabilityRegistryEntry` 增加 read/write roots、network targets/methods、env keys、process targets、timeout、default effect，并让 `contract_digest` 覆盖这些字段。 |
| `python.unittest.locked` 首个内置 capability | 固定 id/version/digest，args schema 只允许冻结 test id，provider forbidden，network/env 默认空，timeout 有上限。最初曾预留 `project:scratch`，现已由 D2-04 runtime 证据收窄为无写权限。 | ACCEPT：需要冻结 test id，拒绝未注册/digest mismatch/越界 args/network/write/process。 | ACCEPT（原 scratch 设计已被后续最小权限修正取代） | 已新增 `python_unittest_locked_registry_entry()`；测试覆盖合法 entry、冻结 args、非白名单 test id 拒绝，以及 digest 随 ceiling 字段变化。 |
| PolicyGrant 与 process scope | 当前 `PolicyGrant` 还没有 process constraint 字段；D2-02 不扩大 grant schema，不把 process effect 做成 grantable effect。 | 尚未达成共识：Claude 建议至少引入 process ceiling，但 root/process 表达仍需进一步定型。 | 尚未达成共识 | Codex 本阶段只把 `process_targets` 放入 registry ceiling，并保持 `policy_grant_matches` 对 `requested_effects.processes` fail closed。真实 executor 前必须重新设计 process 表达。 |
| Approval consumption | D2-02 完整 admission service 若支持 one-time Approval，应在同一事务写 consumption，拒绝 replay。 | conditional ACCEPT：若纳入 Approval，必须覆盖合成 one-time approval replay 拒绝。 | 尚未达成共识 | 本次实现只落地 registry ceiling 与内置 capability 契约；没有新增 admission service，也没有消费 Approval。该条件保留给下一单元。 |
| Budget 范围 | 当前只保留 admission context / ceiling 检查，不实现真实资源计量、reservation、deduction 或 Receipt。 | ACCEPT with condition：必须记录这只是 gate check，不是资源扣减。 | ACCEPT | 已保留 `policy_grant_matches` 的 budget subset 检查，并在记录中明确真实 metering/Receipt 留给 executor 单元。 |
| OpenAPI/runtime 合流 | 因 `CapabilityRegistryEntry` schema 变化，重新导出 D0 baseline OpenAPI 与 TS client；不新增 runtime mutation route。 | 与 D2-00 已知债务一致：runtime SSE 与 baseline app 合流仍是独立决策。 | ACCEPT | 已运行 `scripts/export_vnext_contracts.py` 与 `npm run generate:client`；没有把 D2 runtime route 悄悄混入 baseline app。 |

## 剩余明确未达成共识项

- root token 是否应升级为结构化 root ref，仍未解决；当前 frozen unittest 不再声明未使用的 `project:scratch` 写能力。
- `process_targets` 当前只是 registry ceiling 字段；真实 executor 前，还要决定 process 是 action hash material、capability envelope、grant constraint，还是三者的组合。
- Approval consumption transaction 尚未实现；如果下一阶段做 admission service，必须加入 replay 拒绝测试。

## 实现范围

D2-02 本次仅落地 capability registry ceiling、首个内置 capability 描述、授权函数对 registry ceiling 的 fail-closed 检查、OpenAPI/TS 生成物与证据索引更新。

本次不实现真实 unittest 执行、child process spawn、环境变量透传、stdout/stderr artifact、ActionReceipt、Approval consumption、PolicyGrant consumption、HTTP mutation route、React UI、Tauri 或 OpenAPI/runtime app 合流。

## 验证

- `python -m unittest tests.test_vnext_contracts -v`：通过。
- `python -m compileall nana_sidecar tests scripts`：通过。
- `npm run generate:client`：通过。
- `npm run check`：通过。
- `python -m unittest discover -s tests -v`：`216/216` 通过；保留既有 UI shutdown `gc` ResourceWarning。
