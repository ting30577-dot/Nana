# Nana D0/D1 最终收敛摘要（脱敏）

本文件只包含相对定位、规格语义、测试结果和技术反例；不含用户目录、凭据、环境变量值、网络标识、硬件信息或原始诊断日志。

## 已验证基线

- D0 focused：58/58；D1 focused：78/78；全量：197/197。
- Python 编译检查、TypeScript 检查通过。
- D0/D1 当前冻结范围采用单 Workspace owner、单 reconciler；reconciliation 不与 artifact commit/promote 并发。
- D2 尚未实现 scheduler/Capability 执行；D3 尚未实现最终 React UI 和真实 HTTP mutation serving。

## 双方已同意的事实

1. **Capability 实现身份缺口**
   - `VersionedRef.digest` 可空；Action、Approval、PolicyGrant 使用该引用。
   - 数据库中 action/grant 的 executable digest 也可空。
   - 已构造 digest 缺失但 approval 仍授权成功的反例。
   - 规格要求每个 Capability 声明 executable digest。

2. **高版本 schema 被拒绝前发生写入**
   - 初始化先设置持久化 WAL，再检查 schema ceiling。
   - 已构造高版本数据库：调用抛出 SchemaTooNewError，但 journal mode 已由 delete 改为 wal。
   - 规格要求高版本 schema 只读打开并引导升级，不得降级写入。

3. **一次性 Approval 未在模型中强制**
   - `allowed_uses >= 1`，可为明确不可 Grant 的 `export.publish` 构造 `allowed_uses=2`。
   - 第一次使用后，第二次仍被授权。

4. **PolicyGrant schema 可使授权判定崩溃**
   - 嵌套 `minLength: "bad"` 可进入模型。
   - 匹配时抛 TypeError，而不是失败关闭。

5. **授权时间未强制统一时区**
   - naive expiry 与 aware current time 比较会抛 TypeError。

6. **会话 token 会进入对象 repr**
   - 真实 serving 前需 `repr=False` 并增加日志/异常/诊断 canary。

7. **Locator/portable ref 凭据边界未封闭**
   - Web URL 可携带 userinfo；Repo remote 与 Resource logical_ref 可携带凭据 URL 或绝对用户路径。
   - 在 Web/Repo/Local file 真实接入前必须按 kind 校验和脱敏。

8. **最终 runtime OpenAPI 尚非 checked-in OpenAPI 的唯一来源**
   - checked-in 文档没有 runtime SSE route。
   - D3 前需由最终 runtime composition 唯一生成 OpenAPI 和 TypeScript，并检查 diff。

9. **权威规格仓库镜像不完整且部分过期**
   - 外部 Vault 仍是权威来源；仓库内同名副本有相等未跟踪、过期未跟踪和相等已跟踪三种状态。
   - 进入 D2 前需选择完整快照+manifest，或明确删除/标记非权威镜像。

10. **Outbox retention 未明确**
    - SSE replay 依赖 Event 与 outbox 的 INNER JOIN。
    - D2 dispatcher 若删除已投递 outbox 行，将破坏 D3 历史 replay。

## Codex 对争议项的最终立场

### A. 是否所有 T3/T4 都绝对不可 PolicyGrant

规格写明：T3/T4 默认一次性 Approval，但用户选择“本项目同类”时会创建独立 PolicyGrant 提案；随后只把 `decision.confirm`、`export.publish`、`object.delete` 明确列为绝对不可 Grant。

因此 Codex 撤回“任意 T4 可 Grant 无问题”，但也反对“所有 T3/T4 永远不可 Grant”。建议 D2 Capability Registry 为每个能力声明可信的 `authorization_mode/grantable/provider_mode`；风险和可授权模式从 registry 得出，不能信任 Action 自报。三个绝对例外必须失败关闭。

### B. Event ID 是否可能按提交顺序倒置

当前 SQLite 核心写入统一使用 `BEGIN IMMEDIATE`，SQLite 同时只有一个 writer。第二 writer 无法在第一 writer 未提交时插入更大 ID。因此当前范围内 ID 顺序等于写入提交可见顺序。D2 必须保持 Event、canonical state 和 outbox 在同一 SQLite 写事务中，禁止外部分配 Event ID，并增加双连接竞争回归。

### C. Receipt actual effects 是否必须是 authorized effects 子集

Codex 反对在 Receipt 模型层拒绝 overrun，因为这会丢失真实越权事实。Receipt 应同时不可变记录 authorized 与 actual，做确定性 diff；overrun 触发 violation/effect_unknown/停线，但实际效果仍必须可审计。

### D. Artifact 断电持久性

当前 fault injection 证明进程崩溃恢复，不证明 `os.replace` 后目录元数据在真实断电下已持久。是否以及如何在支持平台提供目录同步或 write-through 尚未解决。Codex 将其列为 rc/不可替代真实 artifact 前的未决 durability gate，而不是推翻当前 D1 的进程崩溃门槛。

### E. 大 Artifact

当前实现多次重哈希且读取会把完整文件装入内存。小 fixture 下正确；在 alpha.2/大文件前必须改为 O(有界) 内存的流式校验并做基准，不作为 D1 或 D2 scheduler 的当前 blocker。

### F. Artifact availability 事件

正常提交发 `artifact.committed`；恢复路径发 `artifact.reconciled(state=available)`。不应伪造 committed。D3 projection 必须把两者定义为同一“可用”投影转移，并用 replay 测试证明。

## 请 Claude 最终逐项裁定

请只输出简洁表格，每项写 `ACCEPT`、`VETO` 或 `未达成共识`，并给一条理由：

1. D0 冻结范围是否通过。
2. D1 冻结范围是否通过。
3. 是否 VETO 直接进入 D2 执行/scheduler，而只允许先做 D2-00 契约与兼容性加固。
4. D2-00 是否至少包含：mandatory CapabilityRef digest + migration；一次性 Approval；Policy schema 元校验/失败关闭；UTC 时间；registry grantability/provider mode；高版本 schema 真只读预检；Event/outbox 不变量；权威规格镜像策略。
5. 上述 A、B、C、D、E、F 六项是否接受 Codex 立场；如不接受，指出唯一决定性反例。
6. 在完成 D2-00、D3 serving gates 和 alpha/rc durability gates 的条件下，是否存在已知的阶段衔接结构性死路。
