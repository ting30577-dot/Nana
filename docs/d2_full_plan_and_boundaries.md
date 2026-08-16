# Nana D2 总规划与边界

本文件用于把 D2 作为一个完整阶段来规划，而不是把 `D2-00`、`D2-01`、`D2-02` 视为互不相干的补丁。它只使用相对模块名和脱敏事实，不包含用户名、绝对路径、token、环境变量值、内网地址、设备序列号或日志凭据。

## 1. D2 阶段目标

D2 的正式目标是建立 Nana 的最小安全执行面：

> 在 D0 contract kernel、D1 Artifact/Event/SSE runtime、D2-00 authorization/storage hardening 的基础上，让 Action 只能通过注册 Capability、冻结授权、scheduler claim、可审计执行和 Receipt 闭环进入副作用世界。

D2 的退出门槛不是“能跑一个测试”，而是：

- 未注册 Capability 不能被调用；
- 参数、路径、网络、provider、process、timeout、budget 越界必须在执行前失败关闭；
- cancel 后不能再启动新 Action；
- budget 达到 100% 时不能再启动 Action；
- 锁定安全语料中未授权 T3/T4/T4-like Action 为零；
- PolicyGrant 只能覆盖满足 capability、参数、目录、网络、预算、期限和 provider 约束的 Action；
- Action 执行后必须产生能追溯授权来源、实际 effect、resource usage 与结果的 Receipt。

## 2. 已完成切片

| 单元 | 状态 | 已证明内容 | 明确未做 |
|---|---|---|---|
| D2-00 authorization/storage hardening | 完成 | Capability digest、registry truth、safe JSON schema、one-time Approval 约束、Receipt/effect audit、locator privacy、schema v2 guard、readonly SSE。 | scheduler、真实执行器、Approval consumption transaction、process kill。 |
| D2-01 scheduler/cancel gate | 完成并经最终修正 | authorized Action 可被一次性 claim；pending cancel；running cancel 使用 `paused/cancel_requested` 等待 executor 结算；`max_actions` count gate；schema v3。 | child process、真实 timeout、budget metering、Receipt。 |
| D2-02 capability ceiling contract | 完成 | `CapabilityRegistryEntry` 携带 capability-level read/write/network/env/process/timeout/default-effect ceiling；`python.unittest.locked` 内置 entry；registry ceiling 进入授权检查；OpenAPI/TS snapshot 更新。 | admission service、Approval consumption、PolicyGrant uses consumption、executor。 |
| D2-03a registry/scope preflight | 完成 | schema v4 用 canonical `entry_json` 保存完整 registry truth；旧不完整 registry rows 升级失败关闭；`CapabilityConstraints` 增加 `process_targets` 精确约束；`python.unittest.locked` read scope 固定为 `project:source` 与 `project:tests`。 | admission service、executor、Receipt、runtime budget。 |
| D2-03b admission service | 完成并经最终修正 | PolicyGrant/Approval 原子消费；schema v6 append-only authorization material；并发/累计预算由数据库事实派生。 | executor、HTTP mutation route。 |
| D2-04 locked executor | 共同 ACCEPT | frozen worker、runtime guard、预算/Receipt；Windows suspended-create→Job-bind→resume；30 个真实孙进程取消 fixture。 | 通用不可信代码 sandbox、任意 shell。 |
| D2-05 runtime budget | 完成并经最终修正 | start reservation、usage ledger、异常/取消路径释放 reservation。 | provider billing、OS 资源强隔离。 |
| D2-06 security corpus | 共同 ACCEPT | 23 手工；360 D2-effective +100 supplemental args-containment；30 个真实孙进程场景；不冒充 future prompt/export stable gate。 | 新业务执行路径、prompt/export runtime gate。 |
| D2-07 handoff | 共同 ACCEPT | handoff v3、replay fixture、orphaned budget/observed-effect 语义、Workspace lock 门槛。 | D3 UI/API、Workspace lock 实现。 |

## 3. 剩余 D2 单元规划

### D2-03a：Registry schema migration、read/process scope 语义冻结

目标：先修正 D2-03 admission service 的三个前置阻塞，保证 admission 后续能从持久化层重建完整 Capability 真相。

已完成：

- SQLite schema v4 将 `capability_registry_entries` 从基础字段表升级为 `entry_json + contract_digest` 表；
- `entry_json` 必须是完整 `CapabilityRegistryEntry` canonical JSON；
- 表级 CHECK 约束固定 capability id/version/digest 与 contract digest 的一致性，并要求 read/write/network/env/process/default-effect 字段存在；
- v3 旧表中若已有 registry rows，则 v4 migration 失败关闭，因为旧 row 无法无损重建 execution ceiling；
- `CapabilityConstraints` 增加 `process_targets`；
- `policy_grant_matches(...)` 对 `requested_effects.processes` 执行精确 subset 检查，不再一律 `process_scope_not_grantable`；
- `python.unittest.locked` 的 registry ceiling 增加 `read_roots=("project:source", "project:tests")`。

不做：

- 不实现 admission service；
- 不消费 Approval 或 PolicyGrant uses；
- 不执行 unittest；
- 不写 Receipt。

### D2-03b：Capability admission service

目标：把 D2-00 授权函数、D2-01 scheduler 和 D2-02 registry ceiling 串成持久化授权准入闭环。

必须：

- 从持久化 registry 查询 `CapabilityRegistryEntry`，不得信任 Action 自报 risk、grantability、provider mode 或 ceiling；
- 从 Action args artifact 读取 canonical JSON，重算 `args_hash`；
- 构造完整 `ActionHashMaterial`；
- PolicyGrant 路径必须使用 `policy_grant_matches(...)`，并在同一事务内完成：
  - grant uses 增量或等价 consumption 记录；
  - Action `proposed -> authorized`；
  - `action.authorized` Event；
  - outbox append；
  - authorization source/ref 持久化；
- one-time Approval 路径必须使用 `approval_authorizes(...)`，并在同一事务内写入 `approval_consumptions`，保证 replay 拒绝；
- 任何不匹配、过期、重放、digest mismatch、schema mismatch、provider mismatch 或 NEVER_GRANT 的 grant 尝试都不得进入 scheduler claim。
- process constraint 必须同时受 registry ceiling 与 Grant `process_targets` 精确 subset 约束。

不做：

- 不 spawn process；
- 不运行 unittest；
- 不写 stdout/stderr artifact；
- 不生成 ActionReceipt；
- 不新增 HTTP mutation route。

退出证据：

- grant hit -> authorized + event/outbox + consumption；
- grant miss -> 无 canonical state 变化；
- approval hit -> authorized + event/outbox + approval consumption；
- approval replay -> fail closed；
- atomic rollback fault injection；
- 双连接竞争下同一 Action 只能授权一次。

### D2-04：Locked local executor for `python.unittest.locked`

目标：实现第一个真实但极窄的执行器，只能运行 registry 冻结的单个 unittest 标识符。

必须：

- executor 只能 claim 已 authorized 的 Action；
- capability 必须是 `python.unittest.locked` 且 digest 匹配；
- test id 必须在 frozen allowlist；
- 不经过 shell，不拼接命令字符串；
- 这是受信 frozen unittest 代码的 locked local executor，不是通用不可信代码 OS sandbox；
- read scope、output cap、network denied、env allowlist 为空、write fail closed、process target 匹配、timeout 上限、cancel race 都是运行时强制约束，不只是测试断言；当前 frozen Action 不请求 scratch write；
- stdout/stderr 有硬上限；
- timeout 到达时终止进程树或把 Action 标 `effect_unknown`；
- cancel race 下不得启动已取消 Action；
- 退出后写入 ActionReceipt，保留 authorization source、authorized effects、observed effects、resource usage、exit metadata 和 result。

不做：

- 不执行用户任意代码；
- 不执行外部下载、包安装或 repo mutation；
- 不支持 T3/T4 能力；
- 不支持外部 export/publish；
- 不开放 UI/API mutation serving。

退出证据：

- 合法 frozen unittest 成功产生 receipt；
- 非白名单 test id、shell metacharacter、未授权网络、越界写入、env leak、超大输出均拒绝；
- timeout/cancel/process crash 均产生可审计终态；
- Receipt effect 超出授权时必须 `effect_violation=true` 且 result 为 `effect_unknown`。

### D2-05：Budget/runtime accounting

目标：把 D2-01 的 count gate 和 D2-03 admission budget context 扩展为真实 runtime accounting。

必须：

- per-action budget、cumulative budget、max uses、max concurrency 与 actual resource usage 可追溯；
- budget 达到 100% 后 scheduler 不得再启动 Action；这个强制点必须在 D2-03/D2-04 启动门预留，D2-05 只是把真实计量接上；
- resource usage 来自 executor receipt 或 fail-closed estimator；
- budget exhaustion 必须是可审计事件或状态转移，而不是静默跳过；
- budget 不得由 Action 自报覆盖。

不做：

- 不建设模型 token/cost 的完整 provider billing；
- 不建设 GPU/内存强隔离；
- 不把 budget metering 伪装成 OS sandbox。

退出证据：

- budget under limit 可执行；
- budget exactly/exceeds limit 阻止新 Action；
- concurrent claim race 下不会超发；
- failed/effect_unknown Action 的 resource accounting 不丢失。

### D2-06：Locked security corpus gate

目标：把 D2 的安全边界转为固定语料，作为进入 D3/alpha.1 前的停线门。

必须覆盖：

- unregistered capability；
- capability digest mismatch；
- args schema mismatch；
- path escape / `..` / symlink / junction；
- shell metacharacter；
- unauthorized network；
- provider unavailable / provider mode mismatch；
- child timeout；
- cancel race；
- oversized output；
- action replay；
- approval expired / content changed / replay；
- T3/T4/NEVER_GRANT grant bypass；
- process target 越界；
- env secret leak。

退出证据：

- 语料版本、seed、trace 可记录；
- 每个反例有明确失败原因；
- 未授权 T3/T4/T4-like Action 通过数为 0；
- 完整 Python、OpenAPI snapshot、TS check 与 manifest 校验通过。

### D2-07：D2 exit review

目标：确认 D2 可以作为完整阶段交付，且不会堵死 D3 UI/API 合流、alpha.1 算法旅程、后续持久记忆和外部工具。

必须：

- 汇总 D2-00 至 D2-06 的证据；
- 对照 D2 退出门槛逐项验收；
- 记录 Codex 与 Claude 对每个关键决策的 ACCEPT、VETO 或尚未达成共识；
- 对未解决项标明是否阻塞 D3；
- 重估 D3 容量；
- 明确 OpenAPI/runtime app 合流是否仍是 D3 决策，不能在 D2 悄悄混入。

不做：

- 不把 D3 React UI、browser SSE client、Tauri、workspace lock、external export 或 alpha.1 业务旅程算作 D2 完成条件。

## 4. 阶段衔接边界

### D0 -> D2

D2 必须继续保持 D0 contract kernel 的约束：

- Action hash 覆盖 capability、args、data class、provider、effects、network methods、budget、risk 和 reversible；
- unknown schema keyword fail closed；
- T4/absolute exception 不可被 grant 预授权；
- OpenAPI/TS schema 只反映公开 contract，不暗示 runtime mutation 已开放。

### D1 -> D2

D2 必须继续保持 D1 runtime 的约束：

- Event、canonical state、outbox 必须在同一 SQLite write transaction；
- outbox retain-only，不删除已投递行；
- SSE 只读连接不得引入写副作用；
- Artifact commit/reconcile 语义不可被 executor 绕开；
- D2 不得引入后台并发 reconciler 或多 owner 假设。

### D2 -> D3

D2 交给 D3 的应该是可控执行事实，而不是 UI 假象：

- D3 可以消费 Action/Event/Receipt/outbox 作为 UI 状态来源；
- D3 不应修补 D2 授权缺陷；
- D3 runtime API 合流必须单独决策；
- UI 只能展示 authorization pending、running、cancelled、effect_unknown、receipt 等真实状态，不得从前端推断授权。

### D2 -> alpha.1

alpha.1 只应在 D2 证明安全执行闭环后开始：

- algorithm fixture 可以使用 `python.unittest.locked` 或后续注册能力；
- 真实问题、Hypothesis、Finding、Decision、export 不属于 D2；
- external publish/export 仍需 one-time Approval 和 Receipt。

## 5. 当前未决项

| 未决项 | 当前状态 | 阻塞对象 |
|---|---|---|
| root token 是否升级为结构化 root ref | D2-03a 仍使用字符串 token；真实 executor 前需定型。 | D2-04 |
| process target 是否进入 Grant constraint | D2-03a 已加入 `CapabilityConstraints.process_targets` 精确匹配；是否升级为更结构化 process descriptor 仍未定。 | D2-04 |
| Approval consumption 数据模型是否足以表达授权来源 | 表结构已存在，但 admission service 未实现。 | D2-03 |
| budget exhaustion 的事件/状态命名 | D2-01 只有 count gate；真实 budget 事件未设计。 | D2-05 |
| executor sandbox 强度 | `python.unittest.locked` 是 locked local executor，不是通用 sandbox。 | D2-04/D2-06 |
| OpenAPI/runtime app 合流 | 已知技术债；D2 不混入，D3 单独决策。 | D3 |

## 6. VETO 边界

以下行为在 D2 阶段明确 VETO：

- 未注册 capability 被 executor 启动；
- 用 shell 字符串执行测试；
- 由 Action 自报 risk、grantable、provider mode 或 effect ceiling；
- 在授权事务之外消费 Approval；
- cancel 后启动新 Action；
- budget 达到或超过 100% 后启动新 Action；
- Receipt 缺失授权来源；
- effect 超出授权却仍写 `succeeded`；
- 为了 UI 方便新增绕过 D2 授权的 mutation route；
- 把 external publish/export/object delete 放进 PolicyGrant 自动授权；
- 把 D3/Tauri/alpha.1 工作混入 D2 完成口径。

## 7. 当前完成性判断

截至 D2-02：

- D2 已完成基础 hardening、scheduler/cancel gate 和 capability ceiling contract；
- D2 还没有完成 admission service、真实 locked executor、runtime budget accounting、安全语料 gate 和 D2 exit review；
- 因此 Nana D2 总目标尚未完成，当前只能说 D2 已进入安全执行面建设的中段。

## 8. Claude 共同审查结论

### 总结

Claude 对本总规划给出的结论是：**有条件 ACCEPT**。

### 必改集合

1. D2-04 必须把 output size cap 与 filesystem read scope 写成运行时强制约束，而不是只放在测试里。
2. D2-04 必须明确其信任假设：它是受信 frozen unittest 的 locked local executor，不是通用不可信代码 sandbox。
3. D2-04 必须作为 executor 接口的一个实现，与 D2-03 授权核心解耦，避免把 D3/alpha.1 的 executor 演进路径堵死。
4. budget 100% 阻断点必须在 D2-03/D2-04 的启动门预留；D2-05 只替换真实计量，count gate 继续保留到 D2-05 上线。
5. D2-03 的 grant/authorization 数据模型必须预留 process constraint 扩展位，但此阶段仍保持 process 由 registry ceiling fail closed。

### 尚未达成共识

- root token 是否要升级为结构化 root ref，仍需后续证据。
- budget exhaustion 的事件/状态命名仍未冻结。
- D2-04 executor 是否以进程内实现还是子进程实现，仍需单独定型。

补充：`python.unittest.locked` 的 `project:source` / `project:tests` read scope 只定义项目可读根；stdlib/site-packages/解释器 import 解析不属于 registry truth，而是 D2-04 子进程 resolver 的职责。

### 结论

上述必改集合已并入本文件的 D2-03/D2-04/D2-05 边界，因此当前总规划可作为 D2 后续执行的基线。
