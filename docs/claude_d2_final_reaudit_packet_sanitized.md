# Nana D2 最终复审包（脱敏）

本文件只包含相对模块名、契约语义和本地测试摘要；不包含用户名、绝对路径、凭据、环境变量值、内网地址、硬件标识或未脱敏日志。

## 评审任务

请以平等共同设计者身份独立审查以下结论。不要默认同意 Codex；请逐项给出：

1. 是否属于 D2 exit blocker；
2. ACCEPT、VETO 或“尚未达成共识”；
3. 最小但完整的修复边界；
4. 需要的反例测试与剩余风险。

## 权威 D2 目标摘要

D2 必须建立最小安全执行面：未注册能力不得执行；参数、路径、网络、provider、process、timeout、budget 越界在执行前失败关闭；cancel 后不再启动新 Action；达到预算上限后不再启动；执行后的 terminal Action 有保留授权来源、授权/实际 effects、resource usage 与结果的 ActionReceipt；锁定安全语料中的未授权高风险通过数为零。

`python.unittest.locked` 是受信 frozen unittest 的窄执行器，不是通用不可信代码沙箱，但 read/write/network/env/process/timeout/output/cancel 仍被 D2 总规划写成运行时强制边界。

## Codex 独立逐项扫描结论

### F1：运行中取消没有 Receipt，也没有终止子进程

- `RunSchedulerService.cancel_run()` 把 running Action 直接改成 `effect_unknown`。
- `LockedUnittestExecutorService` 只在进程启动前检查取消；进程运行期间不轮询 Run/Action 取消状态。
- 被 scheduler 改成 `effect_unknown` 后，executor completion 的 `WHERE state='running'` 必然失败，因而不会写 Receipt，也不会释放 budget ledger 的 running reservation。
- 现有 cancel corpus 只模拟“claim 后、Popen 前”取消，不覆盖运行中取消或真实进程树退出。

Codex 初步结论：**VETO 当前 D2 exit ACCEPT**。建议 running Action 在取消请求后由 executor 负责终止并写 `effect_unknown` Receipt；scheduler 不应抢先把已启动 Action 终态化。需要真实子进程取消、进程树、ledger 释放与 Receipt 测试。

### F2：授权预算没有被 executor 执行

- `ActionHashMaterial.budget` 参与 action hash 与 admission，但没有持久化为 executor 可重建的 authorization material。
- executor timeout 直接使用 registry `timeout_seconds`，output cap 固定为 4096；较小的 per-action Approval/Grant budget 不会生效。
- 因此“授权 1 秒/100 bytes、实际允许运行 60 秒/4096 bytes”是可构造反例。

Codex 初步结论：**VETO**。建议持久化 canonical authorization material（或等价不可变记录），由 executor 重新校验 action hash 后以 registry ceiling、授权 budget 与 Run 剩余预算的最小值执行。

### F3：PolicyGrant admission 信任调用方提供的累计预算与并发上下文

- admission 接收外部 `GrantMatchContext`。
- 只核对 `project_id`；`projected_cumulative_budget` 与 `current_concurrency` 不从 canonical ledger/actions 推导，也不与数据库事实比对。
- 调用方可提交较小累计值或零并发，绕过 grant 的 cumulative budget / max concurrency。

Codex 初步结论：**VETO**。建议 admission 在同一 `BEGIN IMMEDIATE` 事务内从持久化 authorization material、ledger、Action state 与 grant consumption 推导或严格反证 context，不能把它当可信参数。

### F4：locked executor 没有真正强制 read/write/network/process scope

- executor 只比较 Action requested effects 与 registry ceiling。
- 子进程仍拥有当前用户可读文件和网络能力；没有 read-root resolver、写根拦截或 network-denied runtime guard。
- frozen test id 限制减少输入面，但不能证明 runtime boundary 已执行。

Codex 初步结论：按已冻结 D2 规划是 **VETO**。可接受的最小方案应明确只保护受信 frozen Python 测试，并用固定 worker/audit guard 或更强后端限制文件、网络与子进程；若无法形成可信边界，应降低 D2 完成声明而不是把授权校验称为 runtime enforcement。

### F5：runner 异常会遗留 running Action 和预算 reservation

- 非零 exit 会被审计，但 `Popen`/runner 抛异常时 `execute()` 直接向外传播。
- Action 已被 claim，ledger 已 reservation；没有 terminal Action、Receipt 或 usage accounting。

Codex 初步结论：**VETO**。进程是否已产生 effect 无法证明时，应写 `effect_unknown` Receipt；至少保证 reservation 收敛并有结构化错误事件。

### F6：stdout/stderr 双线程 output cap 存在竞态，process-tree kill 失败可被误当成功

- 两个 reader 线程无锁读取共享长度并 append，可能合计超过 cap。
- Windows `taskkill` 无论 return code 是否成功都会提前 return；随后 `wait(timeout=5)` 仍可能再次抛 timeout。
- 现有 output/timeout 测试主要使用 fake runner，没有锁定真实双流上限和子进程树清理。

Codex 初步结论：**VETO**。需要线程安全的共享配额、kill 结果复验、无法清理时 `effect_unknown/orphaned` 语义及真实进程 fixture。

### F7：Receipt 的 actual effects 不是观测值

- locked executor 把 `actual_effects_json` 与 `authorized_effects_json` 写成同一个 requested scope，并固定 `effect_violation=0`。
- registry ceiling 允许 scratch write，但当前 frozen test 并不需要或观测该写入；反之，未受控网络/文件读取也不会被观测。
- 这使 Receipt 看起来闭环，但不能证明真实 effect。

Codex 初步结论：**VETO**。Action 应只申请实际需要的最小 effects；worker/runner 返回结构化 observed effects，Receipt 通过领域模型计算 violation，未知观测则 fail closed。

### F8：D2-06 corpus 对关键 runtime 声明只有模拟或授权层证据

- timeout、oversized output 使用 fake `LockedProcessResult`。
- cancel 只覆盖 Popen 前竞态。
- unauthorized network/process 只调用 authorization matcher，不执行 runtime escape fixture。
- security corpus 因此不能证明 D2 exit review 中的“运行时零越权/进程树清理”。

Codex 初步结论：**VETO 当前 exit gate 证据强度**。修复 F1–F7 后，应把真实 runner 反例加入固定 corpus，再做全量复验。

### F9：Capability 风险级别与执行语义可能偏低

`python.unittest.locked` 会启动进程，registry 还允许 scratch write，但当前 risk tier 为 T1；权威分层把测试、构建、scratch 可逆写归入 T2。

Codex 初步结论：倾向改为 T2，继续允许受限 PolicyGrant；请明确 ACCEPT/VETO 并说明是否需要 capability digest/action fixture 更新。

## 当前本地验证（只证明现有测试没有回归）

- Python compileall：通过。
- D2 focused：95 tests，全部通过。
- TypeScript strict check：通过。
- 这些结果不覆盖上述反例，因此 Codex 不把绿色基线当作 D2 完成证明。

## 请特别反驳

请判断以下辩护是否成立：

1. “frozen test 是受信代码，所以只校验 test id 就等于强制 read/network scope”；
2. “scheduler 把 running Action 标 effect_unknown 已足够，因此不需要 executor Receipt”；
3. “action hash 已包含 budget，所以 executor 不需要读取 budget”；
4. “fake timeout/output 结果足以证明真实 process-tree 与 output cap”；
5. “D2 只是开发切片，可以把上述项全部推迟到 D3”。

请给出一个按依赖排序的修复序列，并明确哪些问题不修就不能把 D2-07 标记为 ACCEPT。
