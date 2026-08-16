# Nana D2 最终共同复审包（脱敏）

本文只含相对模块名、契约语义、测试数量与脱敏错误分类；不含用户名、绝对路径、凭据、环境变量值、内网地址、硬件标识、软件密钥或原始日志。

## 复审要求

请以平等共同设计者身份独立复审，不默认接受 Codex 结论。对 F1-F11 分别给出 `ACCEPT`、`VETO` 或“尚未达成共识”，并列出证据缺口、反例和最小修复。最后判断 D2-07 能否共同 ACCEPT，以及哪些事项只阻塞 D3 真实 mutation serving。

## 当前边界

`python.unittest.locked` 是受信 frozen unittest 的窄执行器，不是任意 hostile-code sandbox。它只运行 registry 冻结 test id；read roots 是 `project:source` / `project:tests`，write/network/env 为空，process target 仅 `builtin:python.unittest.locked`，风险等级 T2。

Storage schema/read ceiling 为 v6。`action_authorizations` append-only 保存完整 ActionHashMaterial、action hash、registry contract digest、authorization source/ref 和 authorization Event ID。D3 不得重新推导授权。

## 逐项修复

### F1：运行中取消与结算

- `cancel_run` 对 running Action 写 Run `paused/cancel_requested`，pending Action 直接取消。
- executor 观察请求、终止进程树、写 Receipt、结算 usage/reservation 后才把 Run 收敛为 `cancelled`；树终止不可验证则 `orphaned`。
- cancel 后等待 250ms，scheduler 仍不得启动新 Action；树必须在 5 秒内退出或显式 orphaned。

Codex：ACCEPT。

### F2：授权 budget 进入 runtime

- timeout 取 registry ceiling、持久授权 material 和 Run snapshot 的最小值；output/artifact cap 取授权 material 与 Run snapshot 的最小值。
- runtime 不信任 Action 或调用者自报预算。

Codex：ACCEPT。

### F3：PolicyGrant 原子事实

- admission 在同一 `BEGIN IMMEDIATE` 事务中从 append-only authorization material 与 Action state 派生累计预算、uses 和 concurrency。
- 伪造低使用量 context 不能绕过 grant ceiling；Approval/Grant consumption 与授权状态/Event/outbox 原子提交。

Codex：ACCEPT。

### F4：runtime scope

- worker 在测试 import 前安装 audit guard；仅把项目源码/测试映射到声明的逻辑 read roots。
- 全部项目写入、网络 socket、child process 与越界读取失败关闭；stdlib/site-packages 是解释器 resolver 范围，不进入 registry truth。
- parent 使用 argv、`shell=False`、空环境、`stdin=DEVNULL`。

Codex：ACCEPT，但只限受信 frozen tests，不主张通用 sandbox。

### F5：runner/Popen 异常

- runner、Popen 或 Job assignment 异常均收敛为 `effect_unknown` Receipt，释放预算 reservation。
- Job assignment 失败会先杀死刚启动 worker 并关闭 pipes，不遗留进程或句柄。

Codex：ACCEPT。

### F6：输出上限与 Windows 进程树

- stdout/stderr 共享锁和总字节配额。
- 30 个真实取消 fixture 证明旧 `taskkill /T` 在当前受限 Windows 宿主 access denied，30/30 无法验证树退出；Codex VETO 旧实现。
- 当前 worker 启动后立即绑定 kill-on-close Windows Job Object；cancel/timeout 调用 `TerminateJobObject` 并等待父句柄，绑定/终止/5 秒退出验证失败均 fail closed。修复后 30/30 通过。

Codex：ACCEPT。

### F7：observed effects

- worker 通过结构化内部帧报告实际读取的逻辑根，parent 添加实际启动的固定 worker process effect。
- 不复制 authorized effects 伪装 observed effects；实际越权必须 `effect_violation=true` 且 result=`effect_unknown`。

Codex：ACCEPT。

### F8：权威 security 数量门槛

- 保留 23 项手工 corpus，明确 version/seed/trace/evaluator/expected reason。
- 新增 460 项矩阵：路径/参数 200、prompt injection 100、合成 credential canary 50、Approval/Grant 变更/过期/重放 50、真实 cancel/process-tree 30、恶意或超大 Artifact 30。
- credential canary 只证明实际存在的 child env/stdout/stderr 边界；D2 没有 prompt/export runtime，不虚构相应动态泄露证明。
- 未授权 T3/T4/T4-like 通过数为 0。

Codex：ACCEPT；此前仅以 23 项退出的结论已被 VETO。

### F9：风险等级与最小权限

- capability 启动固定子进程，因此固定为 T2。
- frozen unittest 不产生 scratch Artifact，registry `write_roots=()`；未来需要写产物必须新增 capability contract/digest 与 resolver，不放宽现有 entry。

Codex：ACCEPT。

### F10：完整持久 registry truth

- schema v4 起用 canonical full `entry_json` 保存 read/write/network/env/process/timeout/default-effect 等完整 ceiling，并由 contract digest 校验。
- 无法重建完整 registry truth 的旧行迁移 fail closed。

Codex：ACCEPT。

### F11：args Artifact 完整性与预算

- admission 和 executor 都在 JSON 解析前校验 persisted size、授权 `max_artifact_bytes`、blob hash 和 canonical args hash。
- size mismatch 使用 `E_ARGS_ARTIFACT_SIZE`，超预算使用 `E_ARGS_ARTIFACT_BUDGET`；executor 在 claim 前拒绝，Action 保持 authorized。

Codex：ACCEPT。

## D2RuntimeHandoff v2

交接固定 Action/Run 状态机、`effect_unknown`、Receipt authorization/effects/usage、structured errors、Event ID/run sequence/aggregate version、retain-only outbox replay、artifact committed/reconciled UI 映射与 command idempotency。提供 replay fixture 与机器 gate。

Workspace lock 生命周期、第二实例失败关闭、SQLite close 后释放 lock、reconciliation 完成后 ready，是开放真实 mutation serving 的硬前置门槛。D3 只读 UI 与 fixture/replay 可以先行；OpenAPI/runtime app 合流仍须显式决策。

## 本地证据

- capability/admission/executor/scheduler/handoff/corpus/matrix 聚焦回归通过。
- quantitative matrices：460 个场景全部通过，其中 30 个为真实 Windows child-process cancel/tree fixture。
- compileall 通过；全量 unittest 265 tests OK；TypeScript strict check 通过；evidence manifest 自检通过；diff check 无 whitespace error（只有既有工作区文件的 LF/CRLF 转换提示）。

## 请重点反驳

1. kill-on-close Job Object 是否仍存在会让 30/30 fixture 产生假阳性的句柄/树竞态？
2. audit hook + frozen allowlist 对“受信测试执行器”的边界是否足够诚实，是否仍有必须阻塞 D2 的读写/网络反例？
3. canonical full registry JSON + digest、append-only authorization snapshot 是否足以让 executor 重建完整授权上限？
4. 460 项矩阵的生成维度是否只是重复样本，哪些缺失维度必须 VETO？
5. `paused/cancel_requested -> cancelled/orphaned` 是否会让 D3 projection 歧义？
6. 除 Workspace lock/OpenAPI 合流外，还有哪些未修就必须 VETO D2-07 的 blocker？
