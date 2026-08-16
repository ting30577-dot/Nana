# Nana D0/D1 最终衔接审计包（脱敏）

> 用途：Codex 与 Claude 对 D0、D1、D0→D1 及其与 D2/D3/后续阶段的衔接做独立审查。
> 本文件只含完成本次技术审计所需的信息；不含硬件信息、用户名、用户目录、网络标识、
> 授权信息、密钥、环境变量值或未脱敏诊断日志。

## 1. 审计问题

请不要依据“测试全绿”直接判定完成。需要分别回答：

1. D0 冻结的 schema、契约、迁移、OpenAPI/TypeScript、状态机、关系、授权输入是否完整；
2. D1 Artifact/Event/Command/SSE runtime 是否真实满足 D1-01～D1-07；
3. D0→D1 的 metadata、事务、Event/outbox、类型和版本边界是否一致；
4. D1 留给 D2 process/action/policy/budget、D3 React/Web、安全生命周期以及更后版本的接口，
   是否存在合法但危险的状态、语义歧义、迁移死角或无法重放的证据；
5. 每项重要结论给出 ACCEPT、VETO 或“尚未达成共识”，并给出可检验的解除条件。

## 2. 当前冻结状态与实际验证

- 当前分支：`codex/v0.3.0-dev-d1-runtime`
- 当前提交：`78850f5`
- D0 checkpoint 未被 D1 amend；D0 49 文件 manifest 重新计算一致。
- D0 focused：58/58。
- D1-01～D1-07 focused：78/78。
- 全量：197/197。
- Python compileall：通过。
- TypeScript `tsc --noEmit`：通过。
- 全量退出仍有一个已隔离到 legacy PySide6 shutdown 的 `gc ResourceWarning`；
  D1 SSE 独立运行不产生该警告。
- 工作树中的用户既有非 D0/D1 核心改动未被清理或覆盖。

这些结果只证明已运行测试；本次审计仍需主动构造反例。

## 3. 权威架构约束摘要

### D0

- 冻结 legacy prototype、inventory、ADR-001～ADR-008。
- schema v1、schema read ceiling、迁移 hash、失败回滚和 dry-run。
- Project/Inquiry/Plan/Run/Action/Event/PolicyGrant/Approval/ActionReceipt/Artifact，
  以及最小研究语义对象。
- Command、状态机、Relation、Locator、授权输入是机器可测试契约。
- 同一 Python 源生成 OpenAPI 与 TypeScript 类型。
- D0 sidecar 只读，明确 `mutations_enabled=false`。

### D1

- `.partial → flush/fsync → hash/size/media type → staged DB/Event/outbox →
  same-volume rename → available DB/Event/outbox`。
- 规格六个 reconciliation 分支各 20 次故障注入；不可用 blob 被读取次数为零；
  收敛后重扫零动作。
- `RevisePlan` 最小真实 Command：command ID 幂等、expected revision、领域变化/Event/
  outbox/CommandResult 同事务；提交前后崩溃和两个连接竞争。
- HTTP SSE：稳定全局 Event ID、Last-Event-ID、catch-up/live 无缝、至少一次传输、
  客户端按 ID 去重、同一 Bearer session 与精确 Origin。
- 10,000 混合 Event 经断线重连后 aggregate version、Run state 和消费投影精确收敛。
- 所有 HTTP 路由默认认证，只显式放行 health、handshake 和必要文档路径。

### 强制后续边界

- 每个 Capability 至少声明 `id/version/executable_digest/args schema/目录/网络/环境/
  副作用/资源限制/risk/Receipt`。
- Action hash 必须绑定 Capability 实现身份、规范参数、数据级别、Provider、实际作用域、
  网络方法、预算、风险和可逆性；内容变化必须使 Approval 失效。
- T3/T4 默认使用一次性 Approval；最终 Decision、发布、删除禁止 PolicyGrant。
- D2 建设 scheduler、process tree、cancel/timeout、Capability、policy、budget、
  Approval/Receipt 和零越权测试。
- D3 使用 `fetch + ReadableStream`，保持 Bearer + 精确 Origin；真实浏览器验证 CORS
  preflight、重连和重复投递。
- 真实 mutation serving、第二实例或业务迁移前，必须取得 OS 级 Workspace 排他锁；
  先锁后开 SQLite/WAL 和 reconciliation，收敛后才 ready；关闭数据库后才释放锁。
- 更高 schema 必须避免降级写，并提供安全的只读打开/升级指引。
- canonical 可移植引用不得保存绝对用户目录；凭据不得进入 SQLite、Artifact、Prompt、
  普通日志或导出。

## 4. 已明确后置、不能误判为当前完成

- D2 scheduler/process/cancel/policy/budget/Capability execution 未实现。
- D3 React 业务 UI、浏览器 CORS/preflight/E2E 未实现。
- launcher、随机端口/bootstrap token、Host/CSRF、Workspace lock 未实现。
- Tauri、PDF、legacy 数据迁移、alpha.1 Decision 与后续产品旅程未实现。

这些未实现项本身不是 D0/D1 失败；但如果 D0/D1 的接口会阻碍、误导或削弱其实现，
必须作为阶段衔接问题报告。

## 5. 审查输出格式

请按严重度列出：

- 事实与代码/契约证据；
- 可构造的失败或误授权场景；
- 当前 D0/D1 是否应保持通过；
- 在进入 D2、D3 或更后阶段前必须关闭的 gate；
- 对可能反驳意见的回应；
- ACCEPT / VETO / 尚未达成共识。
