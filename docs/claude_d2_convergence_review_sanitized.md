# Nana D2 首轮异议修复后二次收敛包（脱敏）

本文只含相对模块名、契约语义、测试事实和合成 fixture；不含用户名、绝对路径、凭据、环境变量值、内网地址、硬件标识、软件密钥或原始诊断日志。

## 请求

Claude 首轮结论为：F2/F3/F9/F10/F11 ACCEPT；F1/F4/F5/F7 conditional ACCEPT；F6/F8 和 D2-07 尚未达成共识。请独立核验下列修复，逐项对 F1/F4/F5/F6/F7/F8/F10 给出 `ACCEPT`、`VETO` 或“尚未达成共识”，最后明确 D2-07 是否可以共同 ACCEPT。不要因为 Codex 已修改就默认接受。

## F6：封闭 Job 绑定窗口

Claude 反例成立：首版 Popen 后 `AssignProcessToJobObject` 存在 worker 在绑定前启动孙进程的窗口。Codex VETO 该实现。

当前 Windows 路径：

1. `subprocess.Popen` 使用固定 argv、`shell=False`、空环境，并带 `CREATE_SUSPENDED`；
2. 通过 process handle 执行 `AssignProcessToJobObject`，Job 使用 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`；
3. 只有绑定成功后才枚举该 PID 的 suspended thread 并 `ResumeThread`；
4. assign/resume 任一步失败时，worker 尚未运行或已处于 Job 中，立即 terminate/kill、等待、关闭 pipes 和 Job；
5. cancel/timeout/output cap 使用 `TerminateJobObject`，等待父句柄；失败或 5 秒内无法确认退出都标记 termination failure。

证据：

- 单测断言调用顺序严格为 assign→resume→close，且 creation flags 包含 `CREATE_SUSPENDED`；
- resume failure 注入证明 suspended worker 被杀、写 `effect_unknown` Receipt、reservation 归零；
- 30 个真实 fixture 的 worker 在 audit guard 安装前立即启动一个真实 Python 孙进程，原子发布孙进程 PID；parent 看到 marker 后 cancel；每项断言父进程终止、孙进程 PID 不存活、延迟 sentinel 未产生、termination verified、总时间 ≤5 秒；
- 30 次真实 `AssignProcessToJobObject` 均成功，否则 fixture 会 fail closed，不会被计为通过。

Codex：ACCEPT 修复后的 F6。

## F8：矩阵有效性与边界诚实性

Claude 反例成立：样本数不能替代独立断言；没有 prompt runtime 时，prompt-like test id 不能冒充 prompt injection gate。Codex VETO 旧表述。

当前 fixture 明确记录：

- executed scenarios = 460；
- D2-effective scenarios = 360；
- future stable full-surface gate = false；
- 100 个 prompt-like strings 仅证明 deterministic frozen-args containment，`counted_in_d2_effective_scenarios=false`；
- 50 个 synthetic canary 仅证明 child env/stdout/stderr，Prompt/log/export 明确 absent/deferred；
- path/parameter 200 分成 13 个 assertion family；
- PolicyGrant 12 个 variant、Approval 10 个 variant，每个断言精确 expected reason；
- malicious/oversized Artifact 7 个 variant，每个断言精确 structured error；
- cancel/process-tree 30 个参数组合，每个都是真实父+孙进程树。

权威规格把完整 prompt/canary 表面数量写在 stable security corpus 门槛；D2 当前没有这些 runtime，因而不宣称通过 future stable gate。D2 exit 只声称当前 narrow execution surface 的零越权证据。

Codex：ACCEPT 修复后的 F8；完整 prompt/export stable gate 明确 deferred，不被降格或伪通过。

## F1/F5：orphaned budget

completion transaction 的顺序为：Action terminal state→Receipt→`record_action_usage`→Action Event→Run settlement。`record_action_usage` 记录保守 usage 并把已结算 Action 的 `running_actions` reservation 减一；随后 termination failure 才把 Run 设为 `orphaned`。

handoff v3 明确：释放 reservation 不代表未知进程已退出；Run quarantine 且不再调度，只避免已形成 Receipt 的 Action 永久占用 concurrency。直接测试断言 orphaned、Receipt=`effect_unknown`、usage 被记录、`running_actions=0`。

Codex：ACCEPT F1/F5 条件已满足。

## F4：bytecode/cache

worker command 从解释器启动即带 `-B`，不是导入后才设置；worker 也在测试 import 前再次设 `sys.dont_write_bytecode=true`。真实 probe 确认该标志为 true。runtime audit guard 对所有 write-mode open 和 filesystem mutation fail closed，因此即使未来误去掉 `-B`，缓存写也不会绕过，而会使 Action 失败关闭。

Codex：ACCEPT F4 条件已满足；仍只主张受信 frozen worker，不是 hostile-code sandbox。

## F7：observed effects

handoff v3 明确 worker self-report 只是 advisory audit evidence。强制阻断由 import 前 audit guard、空环境、fixed argv/schema、Job 与 parent-side authorization/effect subset check 组成；Receipt 不把 self-report 宣传为 OS 级证明。注入越权 observed effect 的测试仍要求 `effect_violation=true` 且 `effect_unknown`。

Codex：ACCEPT F7 条件已满足。

## F10：digest 稳定性

- canonical serialization 固定 `ensure_ascii=false`、`allow_nan=false`、sorted keys、compact separators；
- built-in full registry digest pin 为固定值，并由 contract test 断言；
- 新测试在 schema v4 写入 full `entry_json`/digest，依次执行 v5/v6 migration，再反序列化并断言 entry 与 digest bit-for-bit 不漂移；
- v3 incomplete row 与 v5 missing authorization material 仍 fail closed。

Codex：ACCEPT，补证完成。

## 其他修复

- 删除测试源码中唯一包含用户名的硬编码绝对路径，改为从测试文件推导 workspace root；全仓相应隐私扫描为 0。
- D2RuntimeHandoff 升级为 v3，固定 cancel projection、orphaned budget、observed-effects advisory 语义。

## 当前本地证据

- 修复相关聚焦回归：68 tests OK；
- 30/30 真实父+孙进程 Job fixture OK；
- compileall 通过；
- evidence manifest 刷新与自检通过；
- 最终全量 unittest：269 tests OK；
- TypeScript strict check 通过；diff check 无 whitespace error，仅有既有工作区文件的 LF/CRLF 转换提示；
- unittest 仍只有既有 shutdown `gc ResourceWarning`，退出码为 0。

## 请明确回答

1. suspended-create→bind→resume 加真实孙进程 fixture 是否足以把 F6 转 ACCEPT？
2. 360 D2-effective +100 supplemental/deferred 的诚实分类是否足以把 F8 转 ACCEPT，而不降低 future stable 门槛？
3. orphaned reservation、`-B`、advisory self-report、v4→v6 digest 条件是否分别满足？
4. D2-07 是否可以共同 ACCEPT？若不能，只列仍会阻断 D2 的最小 blocker；请把只阻塞 D3 mutation/stable 的项目分开。
