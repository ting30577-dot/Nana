# Nana D2-04 决策记录

## 最终复审修正

原 D2-04 结论因运行中取消、授权预算、runtime scope、runner exception、双流输出上限、进程树终止验证与 actual effects 证据不足，被 Codex VETO。现已完成：

- timeout/output cap 使用 registry、持久授权材料、Run snapshot 的最小值；
- trusted frozen worker 在测试 import 前安装 Python audit guard，项目 read roots 映射为 `project:source`/`project:tests`，拒绝写、网络和子进程；它仍明确不是通用不可信代码 sandbox；
- worker 结构化报告实际读取的逻辑根，parent 记录固定 worker process effect，不再复制 authorized effects；
- runner/Popen 异常、运行中取消、output truncation、终止不可验证都生成 `effect_unknown` Receipt 并结算预算；
- stdout/stderr 共享总上限；Windows `taskkill /T` 失败不再被 parent-only kill 误报为进程树已验证终止。

历史中间状态：Codex 当时 ACCEPT；Claude 调用因 HTTP 403 `INSUFFICIENT_BALANCE` 未返回实质结论。该段描述的 process group + `taskkill /T` 方案已被后续 30 个真实取消 fixture VETO，并由下节的原生 Windows Job Object 实现取代；当前结论以二审共同 ACCEPT 为准。

## Windows 进程树补审

30 个真实取消 fixture 证明 `taskkill /T` 在当前受限宿主上返回 access denied，原方案只能杀父进程并诚实标记 termination failure，无法提供成功的树终止路径。Codex VETO 原实现并引入原生 Windows Job Object。Claude 首轮又指出“先启动再绑定”仍有孙进程逃逸竞态，Codex接受反例并再次 VETO：当前 Windows worker 以 `CREATE_SUSPENDED` 创建，先 `AssignProcessToJobObject`，再枚举并 `ResumeThread`；任一步失败都杀死尚未运行或已入 Job 的 worker。30/30 fixture 都让 worker 在 audit guard 前立即启动真实孙进程，并验证取消后父/孙进程均在 5 秒内退出。Claude 二审 F4/F5/F6/F7 全部 ACCEPT；D2-04 最终共同 ACCEPT。

最终 frozen unittest 不需要 scratch write，worker 也拒绝所有项目写入，因此 registry `write_roots` 同步收窄为空；这避免 registry truth 声称一个 executor 实际不支持的写能力。未来需要 scratch 产物时必须新增 capability contract/digest 与对应 runtime resolver，不得放宽现有 entry。

## 阶段目标

D2-04 实现第一个真实但极窄的 locked local executor：`python.unittest.locked`。它只能运行 registry 冻结的 unittest id，并在执行后产生可审计 ActionReceipt。

本阶段不实现通用 sandbox、任意 shell、任意用户代码执行、外部下载、包安装、repo mutation、T3/T4 capability、外部 export/publish、HTTP mutation route、D3 UI 或 D2-05 budget accounting。

## 逐项扫描结果

| 扫描项 | 发现 | 处理 |
|---|---|---|
| executor 实现 | 仓库此前没有 D2-04 executor，只有 D2-03b admission 和 D2-01 scheduler。 | 新增 `LockedUnittestExecutorService`。 |
| authorized-only | scheduler 只能 claim authorized Action。 | executor 调用 `RunSchedulerService.claim_action(...)`，非 authorized Action fail closed。 |
| capability identity | `python.unittest.locked` 已有固定 id/version/digest。 | executor 校验 persisted action 与 built-in capability 完全一致。 |
| frozen test id | registry args schema 限定 allowlist。 | executor 从 args artifact 读取 JSON，校验 hash 与 allowlist。 |
| shell / env | D2-04 禁止 shell 字符串执行与环境泄露。 | 默认 runner 使用 argv、`shell=False`、`env={}`、`stdin=DEVNULL`。 |
| read/process/write/network scope | registry ceiling 已固定。 | executor 要求 Action requested effects 等于 locked ceiling；network 必须为空。 |
| cancel race | 初始实现只覆盖启动前已取消。 | 补充 claim 后、process start 前再次检查 state；测试证明 runner 未启动。 |
| timeout/output cap/process crash | D2-04 需要产生可审计终态。 | timeout -> `timed_out`；output cap -> `effect_unknown`；exit nonzero -> `failed`。 |
| Receipt | D2-00 要求 receipt 保留 authorization source、authorized/actual effects、effect_violation。 | executor 写 ActionReceipt，并保留 approval provenance。 |
| Windows process tree | 旧 `taskkill /T` 失败；首版 Popen 后绑定 Job 又有创建竞态。 | `CREATE_SUSPENDED -> AssignProcessToJobObject -> ResumeThread`；30 个真实孙进程对抗 fixture；绑定/恢复/终止/5 秒退出验证失败均关闭。 |

## 决策表

| 决策 | Codex 结论 | Claude 结论 | 当前状态 | 证据 |
|---|---|---|---|---|
| D2-04 只实现 `python.unittest.locked` locked local executor | ACCEPT | 二审 ACCEPT | ACCEPT | `tests.test_d2_locked_executor`。 |
| 默认 runner 使用 argv、`shell=False`、`env={}` | ACCEPT | 二审 ACCEPT | ACCEPT | 真实 frozen unittest 成功测试。 |
| output cap 记为 `effect_unknown` | ACCEPT | 二审 ACCEPT | ACCEPT | `test_output_cap_triggers_effect_unknown_and_truncation_audit`。 |
| timeout 记为 `timed_out` | ACCEPT | 二审 ACCEPT | ACCEPT | `test_timeout_and_output_cap_results_are_audited`。 |
| claim 后 process start 前再次检查 cancel race | ACCEPT | 二审 ACCEPT | ACCEPT | `test_cancel_after_claim_before_process_start_never_reaches_runner`。 |
| Windows Job Object 创建时序 | ACCEPT；必须 suspended-create→bind→resume | 二审 ACCEPT | ACCEPT | `windows_job.py`、创建顺序单测、30 个真实孙进程 fixture。 |

## 验证记录

- `python -m unittest tests.test_d2_locked_executor -v`：7 tests OK。
- 最终补审：包含 admission/executor/scheduler/handoff/corpus/matrix 的聚焦回归 48 tests OK；全量 `python -m unittest` 265 tests OK。
- Claude 反驳修复后：相关聚焦回归 68 tests OK；全量 269 tests OK；30/30 fixture 均含真实孙进程。

## 未决项

- 无 D2-04 blocker。更深树/breakaway 与 hostile-code sandbox 属 stable/未来 backend，不扩张当前受信 frozen worker 声明。
