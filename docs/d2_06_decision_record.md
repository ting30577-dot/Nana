# Nana D2-06 决策记录

## 最终复审修正

Codex VETO 了 timeout/output/cancel 只返回伪造 `LockedProcessResult` 的旧 corpus 证据。该轮 corpus 为 23 项，并使用真实子进程探针覆盖：timeout、运行中 cancel、stdout/stderr 共享 output cap、项目 read scope escape、write、network、child-process。未授权 T3/T4/T4-like 通过数仍为 0。历史中间状态为 Codex ACCEPT、Claude 调用因 HTTP 403 `INSUFFICIENT_BALANCE` 未返回实质结论；后续定量矩阵和二审已经覆盖该状态，当前结论为共同 ACCEPT。

## 权威数量门槛补审

后续完成性审计发现，23 项基础 corpus 没有达到权威规格中的最低数量：200 个路径/参数场景、100 个 prompt injection、50 个 credential canary、50 个 Approval/Grant 变化/过期/重放、30 个含子进程取消 fixture、30 个恶意或超大 Artifact。Codex 因此再次 VETO 旧退出结论。

现新增 `d2_security_matrices.json` 与矩阵 gate，共执行 460 个场景；与 23 项手工基础 corpus 分开保留。Claude 首轮复审指出样本数不能替代有效断言，并 VETO 把不存在的 prompt runtime 写成已通过门槛。Codex 接受：矩阵现明确区分 360 个 D2 有效执行面场景与 100 个 supplemental prompt-like args containment；50 个 canary 只证明 child env/stdout/stderr，完整 Prompt/log/export canary gate 仍未完成。Grant/Approval 的 22 个变化 family 与 Artifact 的 7 个 family 均断言精确失败原因，不再只统计“失败总数”。

30 个取消场景现在使用真实父进程和真实孙进程，并验证 5 秒内整棵 Job 退出。矩阵首次运行发现 Windows `taskkill /T` access denied；Claude 又发现 Popen 后绑定 Job 的理论窗口。最终实现改为 suspended-create→bind→resume，30/30 对抗 fixture 通过。

矩阵还发现 args Artifact 未校验持久 size、也未应用授权 artifact budget；admission 与 executor 现均在解析前以 `E_ARGS_ARTIFACT_SIZE` / `E_ARGS_ARTIFACT_BUDGET` 失败关闭。Credential canary 仅声称覆盖 D2 实际存在的 child env/stdout/stderr；D2 不存在 prompt/export 执行面，不伪造这两个表面的运行证据。

Codex：ACCEPT（VETO 旧的“460 全部等价于 stable gate”表述）。Claude 二审 F8 ACCEPT，确认 360 effective 与 supplemental/deferred 分类没有降低或伪通过 future stable 门槛；D2-06 最终共同 ACCEPT。

## 阶段目标

D2-06 把 D2 的安全边界转为固定语料，作为进入 D3/alpha.1 前的停线门。它不新增业务执行路径，而是把 D2-00 到 D2-05 已实现的强制点串成可审计 security corpus gate。

本阶段不建设通用 sandbox、HTTP mutation route、D3 UI、OpenAPI/runtime app 合流、外部 publish/export 或 provider billing。

## 逐项扫描结果

| 扫描项 | 发现 | 处理 |
|---|---|---|
| unregistered capability | D2-03b admission service 会拒绝未注册 capability。 | 纳入 corpus gate。 |
| capability digest mismatch | authorization contract 与 admission 都校验 digest。 | 纳入 corpus gate。 |
| args schema mismatch | safe JSON schema 与 registry args schema 已 fail closed。 | 纳入 corpus gate。 |
| path escape / `..` | locator logical path validator 已拒绝 absolute/drive/`.`/`..`。 | 纳入 corpus gate。 |
| symlink / junction | D1 artifact boundary 已拒绝 symlink 与 artifact ancestor junction。 | 纳入 D2 security corpus 映射证据。 |
| shell metacharacter | D2-04 executor 不使用 shell，并且 frozen test id schema 不允许 shell payload。 | 纳入 corpus gate。 |
| unauthorized network | registry ceiling / grant constraints 均拒绝越界 network。 | 纳入 corpus gate。 |
| provider mismatch | provider mode 与 allowed providers fail closed。 | 纳入 corpus gate。 |
| child timeout | D2-04 timeout -> `timed_out`。 | 纳入 corpus gate。 |
| cancel race | D2-01/D2-04 均覆盖 cancel race。 | 纳入 corpus gate。 |
| oversized output | D2-04 oversized output -> `effect_unknown`。 | 纳入 corpus gate。 |
| action replay | scheduler claim 后 Action 非 authorized，重放失败。 | 纳入 corpus gate。 |
| approval expired / content changed / replay | D2-00 approval_authorizes 覆盖 expired/hash/uses。 | 纳入 corpus gate。 |
| T3/T4/NEVER_GRANT bypass | NEVER_GRANT 与 one-time approval 规则已在 authorization contract。 | 纳入 corpus gate，要求 unauthorized pass 数为 0。 |
| process target 越界 | D2-03a process_targets subset 已实现。 | 纳入 corpus gate。 |
| env secret leak | D2-04 runner 使用 `env={}`，registry env allowlist 为空。 | 纳入 corpus gate，禁止读取真实 env 值。 |

## 决策表

| 决策 | Codex 结论 | Claude 结论 | 当前状态 | 证据 |
|---|---|---|---|---|
| D2-06 使用固定 JSON corpus + gate test | ACCEPT | 二审 ACCEPT（F8） | ACCEPT | 需要 version/seed/trace，可由 fixture + test 固定。 |
| corpus gate 不新增业务执行路径 | ACCEPT | 二审 ACCEPT（范围确认） | ACCEPT | D2-06 是停线门，不是新 runtime。 |
| 每个反例必须有明确失败 reason | ACCEPT | 二审 ACCEPT（F8） | ACCEPT | 退出证据要求。 |
| T3/T4/T4-like unauthorized pass 数必须为 0 | ACCEPT | 二审 ACCEPT（F8） | ACCEPT | D2 总规划要求。 |
| symlink/junction 映射到 artifact boundary 证据 | ACCEPT | 二审 ACCEPT（范围确认） | ACCEPT | D1/D2 均要求 local path/resource 不可绕过安全边界。 |

## 待验证退出证据

- 语料版本、seed、trace 可记录；
- 每个反例有明确失败原因；
- 未授权 T3/T4/T4-like Action 通过数为 0；
- 完整 Python、OpenAPI snapshot、TS check 与 manifest 校验通过。

## 实现审查中发现并修复的问题

| 问题 | 标记 | 处理 |
|---|---|---|
| unregistered capability fixture 的 expected reason 使用了猜测值 `E_CAPABILITY_NOT_REGISTERED`。 | 错误 | 按真实 admission service 错误码改为 `E_CAPABILITY_UNREGISTERED`。 |
| NEVER_GRANT case 构造了不可能合法存在的 grantable absolute-approval registry entry。 | 错误 | 改为 one-time approval / non-grantable registry entry，再验证 PolicyGrant bypass 被 `capability_requires_one_time_approval` 拒绝。 |
| D2-06 test 直接导入其他 TestCase 类，导致 unittest loader 把被导入测试也当作本模块测试运行。 | 错误 | 改为模块别名引用，避免污染 D2-06 gate。 |
| 修复后再次审查 | 通过 | `python -m unittest tests.test_d2_security_corpus -v`：2 tests OK。 |

## 验证记录

- 权威数量矩阵：7 个 gate tests 覆盖 460 个生成场景，结果 OK；其中 30 个取消场景为真实 Windows 子进程。
- 最终聚焦回归：admission/executor/scheduler/handoff/corpus/matrix 共 48 tests OK。
- Claude 反驳修复后的最终全量回归：`python -m unittest` 269 tests OK。
- `python -m unittest tests.test_d2_security_corpus -v`：2 tests OK。
- `python -m unittest tests.test_d2_security_corpus tests.test_d2_budget_accounting tests.test_d2_capability_admission tests.test_d2_run_scheduler tests.test_d2_locked_executor tests.test_vnext_contracts tests.test_vnext_storage tests.test_vnext_sidecar -v`：89 tests OK。
- `python -m compileall nana_sidecar tests scripts`：OK。
- `python -m unittest discover -s tests -v`：240 tests OK；结尾存在既有 `gc ResourceWarning`，退出码为 0。
- `npm run check`：OK。

## Claude 状态

- 2026-08-01：调用 `scripts/ask_claude.py` 审查 `docs/claude_d2_06_design_packet_sanitized.md`，返回“无法连接 Claude 服务，请检查网络和 NANA_CLAUDE_BASE_URL”。
- `python -m unittest tests.test_claude_reviewer -v`：6 tests OK。
- 上述为历史调用故障；服务恢复后 Claude 二审 F8 ACCEPT，D2-06 已共同收敛。
