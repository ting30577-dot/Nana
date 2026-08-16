# Nana D3 independent proposal from Claude (sanitized)

Claude produced this proposal from
`docs/claude_d3_00_evidence_packet_sanitized.md` without seeing the Codex
proposal. Claude is a read-only co-designer and did not modify the repository.

## 结论

- **最小架构**：五层——Workspace 所有权/OS 锁网关 → D2 事实存储 → 只读投影/Read Model 服务 → 最小突变应用服务（复用 D2 admission/scheduler/executor，绝不旁路）→ 单一「认证 + 默认拒绝」运行时 HTTP/SSE 应用；前端为 fetch+ReadableStream 的 React SPA，画布状态一律由规范事实重建。
- **OpenAPI/运行时应用合并**：**VETO 物理应用合并**（不得把 D0 应用挂载/联合进运行时）；**CONDITIONAL ACCEPT 契约统一**（由认证运行时路由再生成单一 OpenAPI 快照并附回归证据）。
- **顺序网关**：Workspace 锁必须在任何真实突变服务之前通过，且带全套崩溃/二实例/就绪-关闭时序测试。此前只允许只读 UI、fixture/replay、投影、设计。
- **十次连续 E2E + 负态覆盖 + 键盘 + 125%/150% DPI** 作为 D3 出闸硬门槛。
- 存在 **两处实质证据缺口**（D2 是否提供可复用的突变组合入口；一次性审批如何在不重推授权的前提下被写入 action_authorization），在补齐前 D3 的突变段落 **NOT CONSENSUS**。

## 决策依据摘要

| 决策 | 依据 | 标签 |
|---|---|---|
| 锁网关前只读 | real mutation serving 前只允许只读 UI、fixture/replay、投影和设计 | ACCEPT |
| 不合并双应用对象 | D0 OpenAPI app 与 D1 authenticated runtime/SSE app 有意分离；runtime 默认拒绝 | VETO 合并 |
| 契约再生成 | D3 需要 regenerated OpenAPI snapshot/client 与回归证据 | CONDITIONAL ACCEPT |
| SSE 用 fetch+ReadableStream | 浏览器不能用 native EventSource 携带 Bearer | ACCEPT |
| 不重推授权 | 不得查询 PolicyGrant/Approval 重新推导授权 | ACCEPT |
| 突变必须走 D2 | 不得绕过 D2 admission/scheduler/executor | 需新建组合层 |

## 支持与反对证据

**支持架构的证据**

- D2 已具备 admission、scheduling、locked executor、budgets、Receipts、durable authorization material，D3 只需在其上做组合、投影与传输，无需重造执行核。
- 只有 `RevisePlan` 一个突变事务存在；完整 typed command catalog 不等于完整 runtime handlers，因此突变面应收窄到旅程必需集。
- `runs/actions/action_authorizations/events/outbox_events/action_receipts/artifacts`、幂等记录、生命周期投影、结构化错误和 replay fixture 可拼出 dev journey 只读视图，并支持刷新后从 canonical 重建。

**削弱架构的证据**

- 没有 public runtime mutation composition；create/start locked run/approval/export 的组合入口尚不存在，D3 新建突变组合层的规模可能被低估。
- React 与 browser E2E 基础设施尚未安装，十次连续 E2E 代表从零建设测试栈。
- 已知 PySide6 shutdown `ResourceWarning` 表明资源关闭时序存在历史债务，Windows Workspace lock 的 writer quiesce、SQLite/WAL close、lock release 时序容易出错。

## 对常见捷径的反驳

1. **反对物理合并双应用**：把 D0 OpenAPI app 直接挂进 runtime 可能把 D0 的公开/匿名假设带入默认拒绝 runtime。应保留冻结 D0 app，runtime 自带路由并从 runtime 生成新快照。
2. **反对 EventSource / 乐观 UI**：`effect_unknown` 不得是成功；`paused/cancel_requested` 不得是已取消。
3. **反对直接跑测试绕过 executor**：locked test run 必须经 D2 scheduler/executor。
4. **反对跳过 Workspace lock 做演示**：锁是 mutation 前硬门。
5. **反对 blanket CORS/OPTIONS**：仅精确 launch Origin、必要方法和 headers。
6. **反对重试凑十次**：连续十次必须无 flaky retry。

## 收敛条件与可执行建议

### Workspace lifecycle

1. 解析 Workspace 身份并取得 non-blocking process-exclusive OS lock；失败即 fail closed。
2. 持锁下打开 writable SQLite/WAL。
3. migration → reconciliation；收敛后才 `ready`。
4. `ready` 后才开放 mutation routes；ready 前只读投影是否开放待进一步裁决。
5. shutdown：停止 mutation → quiesce writers → close SQLite/WAL → release lock。
6. 测试 OS crash release/restart、second instance denial、ready/close ordering。

### Read models

- RunList；
- RunDetail（含 plan 与 canonical state）；
- ActivityFeed（Events）；
- ArtifactView（保留 reconciled recovery 语义）；
- FindingDraft；
- AuthorizationStatus；
- ReceiptView。

### 最小 mutations

- CreateRun；
- SetResourceLocator；
- RevisePlan；
- StartLockedTestRun（经 D2）；
- DraftFinding；
- RequestOneTimeApproval（经 D2 授权写入）；
- ExportExternalDraft（生成 ActionReceipt）。

显式排除完整 command catalog、alpha.1、hostile-code sandbox、任意 shell/Python、EventSource 与 CORS wildcard。

### React projection/store 与 SSE

- store 仅保留事实投影视图、`last_event_id` 和已见 ID；不保存 canonical 业务真相。
- 先 GET snapshot 得 `snapshot_cursor`，再以 authenticated fetch 和该 cursor 建立 ReadableStream。
- 服务端按 Event ID 有序补发；客户端按 ID 幂等去重，异常顺序失败关闭或重新取 snapshot。
- 心跳和退避重连；刷新等价于重新 snapshot + reconnect。

### E2E matrix

- 完整 happy path。
- authorization pending、running、termination in progress、cancelled、failed、orphaned、`effect_unknown`、reconciled Artifact、Receipt 的独立负态断言。
- reconnect/reload projection consistency。
- second instance、crash recovery、ready/close ordering。
- keyboard path；125%/150% DPI。
- 十次连续无重试全绿。

### Phases

- P0 Workspace lock lifecycle；未过不得进入 mutation。
- P1 read projections + SSE + read-only React shell。
- P2 minimal mutation composition + runtime OpenAPI/client regeneration。
- P3 full journey E2E + negative states + DPI/keyboard + ten consecutive runs。

每阶段保存 compileall、unittest、npm check 与证据摘要。

## 尚未达成共识的问题

1. **突变组合入口是否存在**：D3 新建组合层还是 D2 有预留组合接口？需 D2 handoff 明确入口。
2. **一次性审批写入路径**：哪个 D2 writer 落成 `action_authorization`，而不让 D3 重新推导授权？
3. **Event ID 单调性保证**：需 outbox 排序语义证据。
4. **ready 前是否可提供 canonical read-only SSE/projection**：需时序裁决。
5. **`effect_unknown` UX**：需定义用户可执行动作，不能只显示警告。

Claude stated that these VETO / CONDITIONAL ACCEPT / NOT CONSENSUS labels must
not be softened without evidence.

## Call metadata

- Model: `claude-opus-4-8`
- The gateway returned a complete response successfully.
- Token counters reported by the gateway are preserved in the local invocation
  output but are not treated as product evidence.
