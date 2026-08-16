# Nana D2 总规划审查包（脱敏）

本文件仅包含相对模块名、阶段事实、设计结论和待审问题；不包含用户名、绝对路径、token、环境变量值、内网地址、设备序列号、软件授权、日志凭据或未脱敏诊断信息。

## 当前事实

- D0 contract kernel 已完成。
- D1 Artifact/Event/SSE runtime 已完成。
- D2-00 已完成 authorization/storage hardening：
  - Capability digest、registry truth、safe JSON schema、one-time Approval 约束、Receipt/effect audit、locator privacy、schema v2 guard、readonly SSE。
- D2-01 已完成 scheduler/cancel gate：
  - authorized Action 可被一次性 claim；
  - cancel pending Action；
  - claimed/running Action 标 `effect_unknown`；
  - `max_actions` count gate；
  - schema v3。
- D2-02 已完成 capability ceiling contract：
  - `CapabilityRegistryEntry` 携带 capability-level read/write/network/env/process/timeout/default-effect ceiling；
  - `python.unittest.locked` 内置 entry；
  - registry ceiling 进入授权检查；
  - OpenAPI/TS snapshot 更新。
- 最近验证：
  - `python -m compileall nana_sidecar tests scripts` 通过；
  - `npm run generate:client` 通过；
  - `npm run check` 通过；
  - `python -m unittest discover -s tests -v` 通过 `216/216`；
  - 仍有既有 UI shutdown `gc` ResourceWarning，当前未发现与 D2-02 相关的新失败。

## Codex 当前 D2 总规划

Codex 将剩余 D2 拆为：

1. D2-03 Capability admission service：
   - 从 registry、args artifact 和 authorization contracts 生成持久化授权准入；
   - PolicyGrant hit / Approval hit 在同一 SQLite 事务中完成 consumption、Action authorized、Event/outbox；
   - 不 spawn process，不写 Receipt，不新增 HTTP mutation route。
2. D2-04 Locked local executor for `python.unittest.locked`：
   - 只运行 frozen unittest id；
   - 不经过 shell；
   - network denied；
   - env allowlist 为空；
   - writes restricted to `project:scratch`；
   - timeout/cancel/process crash 产生可审计终态；
   - 执行后写 ActionReceipt。
3. D2-05 Budget/runtime accounting：
   - 从 count gate 扩展到真实 per-action/cumulative/max uses/max concurrency/resource usage；
   - budget 100% 后不得启动新 Action；
   - 不伪装成 OS sandbox 或完整 provider billing。
4. D2-06 Locked security corpus gate：
   - 覆盖 unregistered capability、digest mismatch、schema mismatch、path escape、shell metacharacter、unauthorized network、provider mismatch、timeout、cancel race、oversized output、action replay、approval replay、T3/T4/NEVER_GRANT bypass、process target 越界、env secret leak；
   - 未授权 T3/T4/T4-like Action 通过数必须为 0。
5. D2-07 D2 exit review：
   - 汇总 D2-00 至 D2-06 证据；
   - 对照 D2 exit gate 逐项验收；
   - 记录 Codex/Claude ACCEPT、VETO、尚未达成共识；
   - 明确哪些未决项是否阻塞 D3。

## 明确边界

Codex 当前 VETO：

- 未注册 capability 被 executor 启动；
- shell 字符串执行测试；
- Action 自报 risk、grantable、provider mode 或 effect ceiling；
- 授权事务之外消费 Approval；
- cancel 后启动新 Action；
- budget 达到或超过 100% 后启动新 Action；
- Receipt 缺失授权来源；
- effect 超出授权却仍写 `succeeded`；
- 为 UI 方便新增绕过 D2 授权的 mutation route；
- external publish/export/object delete 被 PolicyGrant 自动授权；
- 把 D3/Tauri/alpha.1 工作混入 D2 完成口径。

## 当前未决项

- root token 是否升级为结构化 root ref；
- process target 是否进入 Grant constraint；
- Approval consumption 数据模型是否足以表达授权来源；
- budget exhaustion 的事件/状态命名；
- `python.unittest.locked` locked local executor 的 sandbox 强度边界；
- OpenAPI/runtime app 合流是否继续留给 D3。

## 请求 Claude 审查

请独立审查并用表格给出 `ACCEPT`、`VETO` 或 `尚未达成共识`：

1. 以上 D2-03 至 D2-07 拆分是否覆盖 `process/action/policy/budget` 与“cancel + zero unauthorized corpus”退出门槛？
2. 是否应把 Approval consumption 放入 D2-03，而不是等到 executor？
3. 是否应在 D2-03 同时扩展 PolicyGrant 的 process constraints，还是保持 process 只由 registry ceiling fail closed，等 D2-04 executor 前再定型？
4. `python.unittest.locked` executor 是否足够作为 D2 第一个真实执行器，还是仍缺少某个必须先实现的边界？
5. Budget exhaustion 应该作为 D2-05 独立单元，还是必须和 D2-04 executor 一起实现？
6. 哪些条目必须 VETO，防止 D2 规划堵死 D3 UI/API、alpha.1 真实算法旅程或后续外部工具？
7. 如果这个规划不完整，请给出最小必改集合，而不是展开到 D3 或 alpha.1 范围。

