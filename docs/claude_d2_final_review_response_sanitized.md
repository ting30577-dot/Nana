# Claude D2 最终复审首轮结论（脱敏记录）

来源：Claude 只读共同设计调用。本文仅记录相对模块、契约结论和测试要求；不含用户名、绝对路径、凭据、环境变量值、内网地址或原始诊断日志。

## 首轮结论

| 项目 | Claude 结论 | 主要理由/收敛条件 |
|---|---|---|
| F1 running cancel | conditional ACCEPT | 明确 `orphaned` 的 reservation/usage 处置。 |
| F2 runtime budget | ACCEPT | registry/material/Run snapshot 取最小值，runtime 不信任自报。 |
| F3 canonical grant context | ACCEPT | `BEGIN IMMEDIATE` 内从持久事实派生 uses/budget/concurrency。 |
| F4 runtime scope | conditional ACCEPT | 明确受信 frozen worker 边界；补 `.pyc`/cache 写入证据。 |
| F5 runner/Popen failure | conditional ACCEPT | 补 `orphaned` reservation 证据。 |
| F6 process tree | 尚未达成共识 | Popen 后再绑定 Job 存在启动前孙进程逃逸窗口；要求 suspended-create→bind→resume 或等价对抗证据。 |
| F7 observed effects | conditional ACCEPT | worker self-report 必须声明为 advisory，不能冒充强制边界。 |
| F8 security matrix | 尚未达成共识 | 460 的样本数不能替代维度独立性；无 prompt runtime 时不得把 prompt-like args 当 prompt gate。 |
| F9 risk/minimum privilege | ACCEPT | T2 与无写权限的 frozen capability 边界一致。 |
| F10 durable registry truth | ACCEPT | canonical full registry JSON + digest + fail-closed migration 足以重建上限；建议补 v4→v6 固定 digest。 |
| F11 args Artifact | ACCEPT | persisted size/budget/blob/canonical material 均在 parse/claim 前校验。 |
| D2-07 | 尚未达成共识（有条件） | F6 与 F8 补齐后可转 ACCEPT。 |

Claude 同时判断 Workspace lock、second-instance、SQLite-close 后释放 lock、reconciliation-before-ready、OpenAPI/runtime 合流和 D3 投影消歧只阻塞真实 mutation serving，不阻塞 D2 本地执行闭环。

## Codex 对首轮反驳的处理

- ACCEPT F6 反例并 VETO 首版 Job 时序；改为 `CREATE_SUSPENDED -> AssignProcessToJobObject -> ResumeThread`，30 个 fixture 均让 worker 在 guard 前立即启动真实孙进程。
- ACCEPT F8 反驳并 VETO “460 全部等价于 stable gate”的旧表述；明确 100 个 prompt-like case 只是 args containment，canary 只是 child env/stdout/stderr partial evidence。
- F1/F5：源码已在进入 `orphaned` 前记录 Receipt/usage 并释放 Action start reservation；新增直接测试和 handoff v3 明文。
- F4：worker 始终以 `-B` 启动，且 probe 确认 `sys.dont_write_bytecode=true`。
- F7：handoff v3 明确 self-report 仅为 advisory audit evidence。
- F10：新增 pinned digest 和 v4→v6 migration round-trip 测试。

上述处理仍需 Claude 二次独立复审，不能由 Codex 单方宣布共同 ACCEPT。
