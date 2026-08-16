# Nana D2-07 设计包（脱敏）

目标：完成 D2 exit review 与 D3 handoff package，确认 D2 能作为完整阶段交付，且不会堵死 D3 UI/API 合流、alpha.1 算法旅程、后续持久记忆和外部工具。本包只包含相对模块名、阶段事实和设计问题，不包含用户名、绝对路径、token、环境变量值、内网地址、MAC、设备序列号、软件授权或未脱敏日志。

## D2 当前完成范围

- D2-00：authorization/storage hardening。
- D2-01：scheduler/cancel gate。
- D2-02：capability ceiling contract。
- D2-03a：full persisted registry truth + read/process scope freeze。
- D2-03b：capability admission service + PolicyGrant/Approval atomic consumption。
- D2-04：`python.unittest.locked` locked local executor + Receipt。
- D2-05：runtime budget accounting。
- D2-06：locked security corpus gate。

## D2-07 Codex 独立设计提案

新增 D2RuntimeHandoff package：

- 人工文档：`docs/d2_runtime_handoff.md`
- exit review：`docs/d2_07_exit_review.md`
- replay fixture：`fixtures/v0.3.0-dev/d2_runtime_handoff_replay.json`
- verification gate：`tests/test_d2_runtime_handoff.py`

handoff 固定以下语义：

1. Run/Action 状态机；
2. `effect_unknown` 的含义：已发生或可能发生副作用，但 D2 无法证明最终效果，D3 不得渲染为成功；
3. ActionReceipt 字段：authorization source/ref、authorized effects、actual effects、effect_violation、result、resource_usage；
4. structured error code 与 reason；
5. Event ID、run sequence、aggregate version 的 replay 规则；
6. outbox retain-only 与 replay 规则；
7. artifact committed 与 reconciled available 的 UI 映射；
8. command idempotency 语义；
9. OpenAPI/runtime app 合流仍是 D3 决策，D2 不新增 mutation route；
10. Workspace lock 生命周期和第二实例测试是 D3/real mutation serving 前置门槛，不算 D2 完成条件。

## 计划验证

`tests/test_d2_runtime_handoff.py` 会验证 fixture：

- handoff version / seed / fixture id 固定；
- event ids 连续；
- per-run `run_seq` 连续；
- per-aggregate `aggregate_version` 连续；
- outbox event ids 与 events 一一对应且 retain-only；
- Receipt 保留授权来源、authorized/actual effects 与 resource usage；
- `effect_unknown` 语义存在且不可映射为 success；
- artifact committed 与 reconciled available 均映射到 UI available；
- command idempotency replay 不产生新 side effect；
- Workspace lock preflight 明确阻止 D3 在 lock 完成前开放真实 mutation serving。

## 请求 Claude 审查

请逐项给出 `ACCEPT`、`VETO` 或 `尚未达成共识`：

1. D2-07 是否应以 `docs/d2_runtime_handoff.md` + replay fixture + verification gate 的形式交付？
2. 上述 handoff 语义是否足以防止 D3 重新推导授权、把 UI 状态当事实来源、或绕过 D2 执行？
3. OpenAPI/runtime app 合流继续留作 D3 决策是否正确？
4. Workspace lock 作为 D3/real mutation serving 前置门槛、不算 D2 完成条件，是否正确？
5. 是否存在必须 VETO 的缺口，尤其是 Event/outbox replay、artifact reconciled UI 映射、effect_unknown、command idempotency 或 structured error code？
