# Nana D2-04 设计/实现包（脱敏）

目标：实现第一个真实但极窄的 locked local executor：`python.unittest.locked`。本包只包含相对模块名、阶段事实和本地测试证据，不包含用户名、绝对路径、token、环境变量值、内网地址、设备序列号、软件授权或未脱敏日志。

## 当前本地实现

- 新增 `nana_sidecar.storage.locked_unittest_executor.LockedUnittestExecutorService`。
- 只接受已 authorized 的 Action；通过 D2-01 `RunSchedulerService.claim_action(...)` 原子 claim 到 running。
- 只允许 built-in capability `python.unittest.locked` 的固定 id/version/digest。
- 从 args artifact 字节读取 JSON，校验 artifact blob hash、args hash、frozen test id allowlist。
- 校验 Action requested effects 必须等于 registry ceiling：
  - reads: `project:source`, `project:tests`
  - writes: `project:scratch`
  - processes: `builtin:python.unittest.locked`
  - network: empty
- 默认 runner 使用 argv 形式 `[python, -m, unittest, test_id]`，`shell=False`，`env={}`，`stdin=DEVNULL`。
- stdout/stderr 有硬上限；超出时终止进程并把 Action/Receipt 记为 `effect_unknown`。
- timeout 会终止进程树或进程，并把 Action/Receipt 记为 `timed_out`。
- process exit 0 -> `succeeded`；nonzero -> `failed`。
- cancel race：
  - 启动前已非 authorized：不启动；
  - claim 后、process start 前被取消/变更：再次检查 state，不启动 runner。
- 完成后写 `ActionReceipt`，保留：
  - authorization source/ref；
  - approval provenance；
  - authorized effects；
  - actual effects；
  - resource usage；
  - exit code；
  - `effect_violation=false`。
- 写 completion/event/outbox 与 receipt 在同一事务中完成。

## Codex 独立判断

- 这是受信 frozen unittest 的 locked local executor，不是通用 OS sandbox。
- D2-04 不新增 HTTP mutation route，不做 D3 UI，不做外部 export/publish，不做通用 shell，不做任意用户代码执行。
- 解释器、stdlib、site-packages/import resolver 不属于 registry truth，而属于 executor runtime 解析边界；本地实现通过仓库根执行 frozen test id。
- Windows Job Object 级 process-tree 控制仍可在后续加强；当前默认 runner 使用 process group/taskkill/kill 的最小可测实现，并通过测试覆盖 timeout 分支。

## 本地验证

- `python -m unittest tests.test_d2_locked_executor -v`：7 tests OK。
- 已覆盖：
  - 真实 frozen unittest 成功；
  - 已取消 Action 不启动 runner；
  - claim 后 process start 前取消不启动 runner；
  - timeout 审计；
  - oversized output -> `effect_unknown`；
  - exit nonzero -> failed；
  - approval provenance 写入 receipt。

## 请求 Claude 审查

请独立审查并逐项给出 `ACCEPT`、`VETO` 或 `尚未达成共识`：

1. 该 D2-04 executor 是否满足“第一个真实但极窄的 locked local executor”，且没有越界成通用 sandbox？
2. 当前 claim -> pre-start cancel check -> process runner -> receipt/event/outbox 的顺序是否足以作为 D2-04 最小实现？
3. `shell=False`、argv、`env={}`、frozen test allowlist、args artifact hash 校验是否足以满足本阶段的命令/环境边界？
4. output cap -> `effect_unknown`，timeout -> `timed_out`，exit nonzero -> `failed` 的审计语义是否正确？
5. Receipt 字段是否足够支撑 D2-05 budget/runtime 和 D3 handoff？
6. 是否必须在 D2-04 现在引入 Windows Job Object，否则应 VETO？
