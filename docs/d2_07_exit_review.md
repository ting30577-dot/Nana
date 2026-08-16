# Nana D2-07 Exit Review

## 2026-08-01 最终复审修正

Codex 对 D2 全链路重新逐项扫描后，VETO 了此前的本地退出结论，并列出 F1-F9 九项问题。现已逐项修复并重新审查：

| 编号 | 原问题 | 修复与证据 | Codex 状态 | Claude 状态 |
|---|---|---|---|---|
| F1 | running cancel 直接写 `effect_unknown`，没有 Receipt/kill，预算 reservation 卡住 | 改为 Run `paused/cancel_requested`；executor 停止并结算后写 Receipt、释放 reservation，再将 Run 收敛为 `cancelled`；终止不可验证则 `orphaned` | ACCEPT | ACCEPT（二审） |
| F2 | executor 忽略授权的 timeout/output budget | runtime 上限取 registry、持久授权材料、Run snapshot 的最小值；测试验证 7 秒/123 bytes 传入 runner | ACCEPT | ACCEPT（首审） |
| F3 | admission 信任调用方上报并发/累计预算 | 改为从 append-only `action_authorizations` 与 Action state 原子派生；伪造低预算 context 不能绕过累计门槛 | ACCEPT | ACCEPT（首审） |
| F4 | read/write/network/process 仅有声明、无 runtime enforcement | trusted frozen worker 在导入测试前安装 audit guard；项目读根映射为 `project:source`/`project:tests`，写、网络、子进程均拒绝；stdlib/site-packages 作为 resolver 范围单独处理 | ACCEPT（仅限受信 frozen test，不是通用 sandbox） | ACCEPT（二审，同一范围） |
| F5 | Popen/runner 异常遗留 running Action | runner 异常统一结算为 `effect_unknown` Receipt 并释放预算 | ACCEPT | ACCEPT（二审） |
| F6 | stdout/stderr cap 竞争与进程树终止误报 | 两流共享总上限；Claude 又发现 Popen 后绑定竞态，现改为 suspended-create→Job-bind→resume，30 个 fixture 都启动真实孙进程并验证整树退出 | ACCEPT | ACCEPT |
| F7 | actual effects 复制 authorized effects | worker 通过结构化帧报告实际读取的逻辑根；parent 增加已观察到的固定 worker process effect；越权实际效果测试要求 `effect_violation=true` | ACCEPT | ACCEPT（二审） |
| F8 | security corpus 的 timeout/output/cancel 只是伪造结果 | 23 项手工 corpus；矩阵执行 460 场景，但明确只有 360 个 D2-effective，100 个 prompt-like args 不冒充 prompt runtime gate；authorization/artifact 精确 reason family | ACCEPT（VETO 旧全量 stable-gate 表述） | ACCEPT |
| F9 | 启动子进程的 capability 标为 T1 | `python.unittest.locked` 固定为 T2，registry/action/grant/fixture 一致 | ACCEPT | ACCEPT（首审） |

此外，schema 升级到 v6，新增 append-only `action_authorizations`，完整持久化并绑定 ActionHashMaterial、registry contract digest、authorization source/ref 与授权 Event。v5 若已有无法重建授权材料的 Action，迁移 fail closed。

Claude 首轮给出 F6/F8 反例后，Codex 完成 suspended Job 时序、真实孙进程 fixture、矩阵有效性重分类及其余补证；Claude 二审对全部 conditional/未共识项转为 ACCEPT，并明确 D2-07 共同 ACCEPT。

修复完成后曾使用 `docs/claude_d2_final_resolution_review_sanitized.md` 发起逐项 F1-F9 复审，服务端当时再次返回同一 HTTP 403；这是历史调用故障，不是最终审查状态。服务恢复后的首审与二审响应分别记录在 `docs/claude_d2_final_review_response_sanitized.md` 和 `docs/claude_d2_convergence_response_sanitized.md`，最终结论为共同 ACCEPT。

最终本地验证：`python -m compileall nana_sidecar tests scripts` 通过；`python -m unittest` 为 256 tests、结果 OK；`npm.cmd run check` 通过。unittest 结束时仍有既有 `gc ResourceWarning`，但退出码为 0。

## 权威数量门槛补充审计

上一条“最终验证”随后被更严格的规格对照推翻：基础 security corpus 只有 23 项，未达到权威规格的定量门槛。新增的定量矩阵覆盖 460 个场景：路径/参数 200、prompt injection 100、credential canary 50、Approval/Grant 50、真实取消/进程树 30、恶意或超大 Artifact 30。

矩阵发现并修复两项新 blocker：Windows `taskkill /T` access denied 导致 30/30 进程树终止不可验证；args Artifact 缺少 persisted size 与授权 artifact budget 校验。前者以原生 Windows Job Object 修复，后者在 admission/executor 双入口失败关闭。新的全量验证结果以本节后续证据记录为准；旧的 256 tests 数字保留为审计历史，不再代表最终门槛。

## Claude 首轮反驳后的补充停线审查（R1-R5）

首轮复审又发现并处理：

下表使用 `R1` 至 `R5` 作为补充审查编号，避免与最终 review packet 中既有的
F1-F11 重名。其中 R1 是 F6 Windows Job 反例的加固，R4 包含 F10 registry digest
补证；它们不是新的 F10-F14。

| 编号 | 问题 | 处理 | Codex | Claude |
|---|---|---|---|---|
| R1 | Popen 后绑定 Job 存在启动前逃逸窗口 | `CREATE_SUSPENDED -> AssignProcessToJobObject -> ResumeThread`；30/30 真实孙进程 fixture | ACCEPT | ACCEPT |
| R2 | 460 样本可能重复或空断言 | 360 D2-effective + 100 supplemental；22 authorization 与 7 artifact 精确 reason；stable gate 明确未完成 | ACCEPT | ACCEPT |
| R3 | `orphaned` reservation 处置不明 | Receipt/usage 后释放 start reservation，Run quarantine，禁止继续调度；handoff v3 固定 | ACCEPT | ACCEPT |
| R4 | `.pyc`、observed effects、digest 证据弱 | `-B` probe；self-report advisory；pinned digest + v4→v6 round-trip | ACCEPT | ACCEPT |
| R5 | 测试源码含用户名绝对路径 | 改为从测试文件推导工作区根，隐私扫描为 0 | ACCEPT | 无异议 |

Claude 首轮反驳修复后的最终验证：`python -m compileall nana_sidecar tests scripts` 通过；相关聚焦回归 68 tests OK；`python -m unittest` 为 269 tests、结果 OK；`npm.cmd run check` 通过；evidence manifest 自检通过；`git diff --check` 仅报告既有工作区文件的 LF/CRLF 转换提示，无 whitespace error。unittest 仍只出现既有 shutdown `gc ResourceWarning`，退出码为 0。

## 结论

Codex 本地结论：D2-00 至 D2-06 的本地实现与验证证据已经形成可交付的 D2 安全执行闭环；D2-07 通过 `D2RuntimeHandoff` 文档、replay fixture 与 verification gate 固定交给 D3 的事实来源。

Claude 最终状态：二次收敛复审对 F1/F4/F5/F6/F7/F8/F10 全部 ACCEPT，并明确 D2-07 可以共同 ACCEPT、无剩余 D2 blocker。共同口径严格限定为“受信 frozen worker 当前窄执行面的零越权证据”。

ResourceWarning 补证：capability admission、run scheduler、locked executor、budget accounting、security corpus、security matrices、runtime handoff 七个 D2 测试模块共 55 tests 在 `ResourceWarning` 视为错误时通过；警告可由任意单个迁移期 `test_ui_smoke` 复现，而 D1 runtime/SSE 与 D2 模块不复现。因此归属 PySide6 `QApplication/MainWindow` shutdown 生命周期，不涉及 D2 Job、pipe 或 process handle，作为非阻塞既有 UI 债务记录。

## 阶段证据汇总

| 阶段 | 状态 | 关键证据 |
|---|---|---|
| D2-00 authorization/storage hardening | 完成 | capability digest、registry truth、safe JSON schema、Receipt/effect audit、locator privacy、schema hardening。 |
| D2-01 scheduler/cancel gate | 完成 | authorized Action 单次 claim、cancel pending/running、count gate、append-only Event/outbox。 |
| D2-02 capability ceiling contract | 完成 | `python.unittest.locked` registry ceiling，read/write/network/env/process/timeout/default-effect。 |
| D2-03a registry/scope preflight | 完成 | schema v4 full registry JSON，process/read scope 语义冻结。 |
| D2-03b admission service | 完成 | PolicyGrant/Approval 原子消费，args/action hash/registry binding。 |
| D2-04 locked executor | 共同 ACCEPT | frozen executor、suspended Job bind、真实孙进程 cancel、timeout/output/Receipt。 |
| D2-05 runtime budget accounting | 完成 | schema v5 budget ledger、start reservation、receipt usage accounting。 |
| D2-06 security corpus gate | 共同 ACCEPT | 23 手工；360 D2-effective +100 supplemental；30 个真实孙进程 fixture；高风险越权 0。 |
| D2-07 handoff | 共同 ACCEPT | handoff v3、schema v6 authorization binding、orphaned budget 与 observed-effect 语义。 |

## D2 exit gate

| Gate | 结果 | 证据 |
|---|---|---|
| 参数、路径、网络、provider、process、timeout、budget 越界执行前 fail closed | 通过 | D2-00/D2-03/D2-04/D2-05/D2-06 tests。 |
| cancel 后不能启动新 Action | 通过 | D2-01/D2-04/D2-06 tests。 |
| budget 达到 100% 后不能启动 Action | 通过 | D2-05 tests。 |
| Approval/PolicyGrant replay 不得重复授权 | 通过 | D2-03b/D2-06 tests。 |
| 每次已启动执行必须有 Receipt 并保留授权来源；runner 异常/运行中取消也不得例外 | 通过 | D2-04 runner-error/running-cancel tests。 |
| effect overrun 必须 `effect_violation=true` 且 `effect_unknown` | 通过 | D2-04 observed-effect violation test。 |
| security corpus 未授权 T3/T4/T4-like 通过数为 0 | 通过 | D2-06 tests。 |
| D3 handoff 可 replay | 通过 | D2-07 handoff tests。 |

## 未解决项与 D3 阻塞性

| 未解决项 | 当前状态 | 是否阻塞 D3 |
|---|---|---|
| stable prompt/credential 全表面 gate | D2 没有 prompt/log/export runtime；当前不宣称通过完整 stable gate。 | 不阻塞 D2 窄执行闭环；阻塞相应 runtime/stable 发布。 |
| orphaned 全局真实资源监控 | reservation 已释放但未知进程理论上可能仍耗用资源；Run 已 quarantine。 | 不阻塞 D2；D3/stable 需监控/量化上界。 |
| 更深进程树/breakaway corpus | 当前 30 个 fixture 为真实深度 1 孙进程，未开启 BREAKAWAY_OK。 | 不阻塞 D2；stable 加固项。 |
| OpenAPI/runtime app 合流 | D2 保持 D0 baseline，不新增 mutation route。 | D3 API 合流前置决策。 |
| Workspace lock 生命周期 | D2 不实现。 | 阻塞 D3 真实写入服务，不阻塞只读 UI 或 replay fixture。 |
| 更细 effect violation taxonomy | 当前 boolean audit bit。 | 不阻塞 D3；可后续增强 UI 分类。 |

## D3 容量重估

D3 首批建议范围：

1. 只读 UI / replay fixture viewer；
2. D2RuntimeHandoff projection；
3. runtime app/OpenAPI 合流设计；
4. Workspace lock lifecycle；
5. 真实 mutation serving 前的 second-instance / ready-order tests。

D3 不应：

- 重新推导授权；
- 绕过 D2 scheduler/admission/executor；
- 把 UI local state 当事实；
- 在 Workspace lock 前开放真实写入服务；
- 把 external publish/export/object delete 放入 grant 自动授权。
