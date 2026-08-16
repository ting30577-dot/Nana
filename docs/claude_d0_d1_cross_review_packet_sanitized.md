# Nana D0/D1 最终交叉审议包（脱敏）

> 本包用于 Codex 与 Claude 的双向反驳与显式收敛。只含相对文件定位、代码事实、
> 测试结果和技术论据；不含硬件、用户名、用户目录、网络标识、授权信息、密钥、
> 环境变量值或未脱敏日志。

## 1. 共同起点

- D0 focused 58/58、D1 focused 78/78、全量 197/197、compileall、TypeScript check
  均通过。
- D0/D1 当前冻结范围不应因后续功能尚未实现而被倒推为失败。
- 但任何会让 D2/D3/后续阶段合法构造危险状态、改写安全语义或无法重放权威证据的
  接口，都必须作为衔接 gate。
- 当前代码仍只允许单 Workspace owner、单 reconciler，且 reconciliation 不与
  commit/promote 并发；真实 serving 前必须实现 Workspace lock 与 ready 顺序。

## 2. 双方已独立确认的高优先级问题

### C1 Capability 实现身份未成为必填授权材料

代码事实：

- `VersionedRef.digest` 可空；
- `ActionHashMaterial`、`Action`、`PolicyGrant`、`Approval` 和相关 Command 使用
  `VersionedRef`；
- schema 的 `actions.executable_digest` 与
  `policy_grants.executable_digest` 可为 `NULL`。

实际反例：

- digest 缺失的 Action material、Approval 可以通过模型校验；
- `approval_authorizes(...).matches == True`；
- 同 id/version 的实现替换不会改变 action hash。

Codex：VETO D2 执行面。应增加专用、digest 必填的 `CapabilityRef`，并通过新迁移
加固持久层；执行前再次比较实际加载实现的 digest。

Claude：VETO D2，理由一致。

### C2 高版本 schema 在拒绝前已被修改

代码事实：

- `initialize_database` 先以读写方式打开，再执行持久化
  `PRAGMA journal_mode=WAL`，随后才验证 schema ceiling/history。
- `connect_database` 与 SSE 也没有真正的只读连接入口。

实际反例：

1. 建立 `user_version=2`、journal mode 为 `delete` 的数据库；
2. 调用 `initialize_database`；
3. 得到 `SchemaTooNewError`；
4. 重新检查数据库，journal mode 已变为 `wal`。

Codex 与 Claude：VETO 更高 schema 的安全打开语义。任何写 PRAGMA 前必须只读检查；
提供真正 `mode=ro` 的 inspection/SSE 路径；更高 schema 不得被旧应用修改。

## 3. Codex 独立发现、Claude 第一轮未覆盖的问题

### C3 一次性 Approval 未强制

- `Approval.allowed_uses >= 1`，无与 capability/risk/reversible 的交叉约束；
- 为 `export.publish` 构造 `allowed_uses=2` 后，
  `prior_uses=1` 仍被 `approval_authorizes` 接受。

Codex：至少三个明确禁止 Grant 的 Capability，以及任何规范明确为“一次性”的
Action，必须在契约和持久层强制单次；D2 还必须原子消费授权/Action 状态。

### C4 PolicyGrant JSON Schema 可以让判定器抛异常

- `CapabilityConstraints.args_schema` 接受任意 JSON object；
- 嵌套 `{"type":"string","minLength":"bad"}` 可通过模型构造；
- 当实际参数走到该字段时，`policy_grant_matches` 抛出 `TypeError`，而不是返回拒绝。

Codex：D2 前必须对支持的 schema 子集做递归元校验；所有不合法 schema 创建时拒绝，
匹配时仍失败关闭为明确原因，不能使 policy engine 崩溃。

### C5 授权时间没有统一时区约束

- Pydantic datetime 同时接受 naive/aware；
- naive `expires_at` 与 aware `at` 比较会抛 `TypeError`。

Codex：所有 canonical/authorization 时间必须强制 timezone-aware UTC，或在边界统一
规范化；加入混合时区反例。

### C6 会话 token 会进入对象 repr

- `LocalSession` 是默认 frozen dataclass；
- `repr(LocalSession(...))` 包含完整 token。

Codex：在 D3/launcher 真实 serving 前将 token 字段设为 `repr=False`，并加入
日志/异常/诊断 canary；这不推翻 D1 认证逻辑，但属于凭据泄露硬化 gate。

### C7 Web/Repo locator 与 portable ref 的凭据/路径边界未闭合

- `WebCoordinates.canonical_url` 接受带 username/password 的 URL；
- `RepoCoordinates.remote`、`Resource.logical_ref` 是一般字符串；
- 目前可把含凭据 URL 或绝对用户目录构造成合法 canonical DTO。

Codex：在 alpha.1 Web Resource、alpha.2 Repo/Local file 接入前，必须引入按 kind
校验的安全 locator/ref：拒绝 URL userinfo，处理敏感 query，Git remote 去凭据，
本地路径只存 Workspace-relative logical ref 或受控 token。

### C8 checked-in OpenAPI 不是 D1 runtime OpenAPI

实际结果：

- checked-in `nana_web/openapi.json` 只有 health/handshake/contracts；
- `create_runtime_app().openapi()` 还包含 `/api/v1/events`；
- generated TypeScript paths 不含 SSE route。

Codex：这是 D0 冻结设计下的诚实后置项，不 VETO D1；但 D3 前必须建立“最终 runtime
composition → checked-in OpenAPI → generated client”的唯一生成入口，并对 diff
做 gate。Run/Action/Approval/Budget 等 Event payload 也应在 D3 消费前形成可判别
的 typed union，不能只靠 `dict[str, unknown]`。

### C9 权威规格的仓库镜像不完整

- 权威来源始终是外部 Vault，当前 07/11/12 的仓库副本与权威 bytes 一致并已跟踪；
- 00/06 副本一致但未跟踪；
- 05/10 副本既未跟踪又落后于权威版本。

Codex：不影响当前运行时测试，但影响新环境重放完整架构依据。进入 D2 前应选择并
记录一种明确策略：要么跟踪完整 13 份权威快照与 manifest，要么删除/标记非权威
镜像，避免同名旧规格误导后续开发。

## 4. Claude 提出、Codex 的回应

### D1 “任意 T4 必须被 PolicyGrant 拒绝”

Claude 第一轮：`policy_grant_matches` 只拒绝三个 capability id；任意新 T4 id 可由
Grant 匹配，故 VETO。

Codex 反驳：

- 权威规格写明 T3/T4 默认一次性 Approval，但用户选择“本项目同类”时会创建独立
  PolicyGrant 提案；随后只把 `decision.confirm / export.publish / object.delete`
  写成绝对不可 Grant 的例外。
- 因而“所有 T3/T4 永远不可 Grant”并非当前已确认语义。
- 但仅靠三个字符串同样脆弱。D2 Capability Registry 应有确定性的
  `authorization_mode/grantable` 元数据，Policy Engine 从注册能力读取，不能信任
  Action 自报 risk，也不能让新命名绕过绝对例外。

请求 Claude：在看到上述文本后，撤回 blanket VETO、维持 VETO，或标为规格歧义；
必须说明依据。

### D2 `provider=None` 绕过 allowlist

Claude：grant 有非空 allowed providers、material.provider=None 时匹配，可能绕过。

Codex：`None` 对纯本地确定性能力可能正确表示“不使用 Provider”；通用 matcher
无法仅据此拒绝。真实缺口是 Capability contract 没声明 provider 是否 required。
建议 D2 Registry 声明 provider mode，云/模型能力必须提供 provider，本地能力必须
为 None；Grant 再按该规范匹配。

请求 Claude：判断这是当前通用 matcher 漏洞，还是 D2 Capability 元数据 gate。

### D3 SQLite 多写者会让 Event ID 按提交乱序

Claude：若低 ID 事务晚提交，SSE 最大 cursor 会跳过。

Codex 反驳：

- SQLite 同一数据库任一时刻只有一个 writer；
- D1 的 Artifact、reconciler、Command 全部在写入前使用 `BEGIN IMMEDIATE`；
- 第二 writer 无法在第一 writer 未提交时插入更高 ID；
- 因而多连接不等于并行提交乱序，当前 ID 顺序与提交可见顺序一致。

Codex 同意把“所有 Event 与 canonical change 在同一 SQLite 写事务中完成；禁止外部
预分配 ID”写为 D2 不变量，并加入多连接并发回归，但不接受把当前实现定为缺陷。

### D4 Receipt actual effects 不应大于授权 effects

Claude：建议模型 validator 强制 `actual ⊆ authorized`。

Codex 反驳：Receipt 是实际发生事实的不可变证明。如果工具越权，拒绝写入 Receipt
会抹去最需要审计的事实。正确做法是同时保存 authorized/actual，确定性比较，
越界时标记 policy violation / `effect_unknown`、停线并产生 Event，而不是禁止记录。

### D5 `CORRUPT/FAILED → AVAILABLE` 会洗白

Claude 第一轮：ArtifactReconciledPayload 没重复 hash/size，可能洗白。

Codex：canonical Artifact row 已绑定 blob_hash/size；当前 reconciler 只执行
staged→available/failed 与 available→corrupt，且转 available 前验证 final bytes。
未来恢复路径仍必须复用同一验证器。Event 不必重复全部 metadata，但 typed payload
或投影谓词必须清楚。

### D6 rename 后缺少目录 fsync

Claude 第二轮：真实断电可能出现 DB 已 committed、目录项未持久，倾向真实 serving
前硬 gate。

Codex：

- D1 已证明的是进程崩溃/注入窗口与“不可用内容不被读”，不是突然断电下零数据损失；
- 权威协议要求 partial file flush/fsync 与同卷 rename，并写“平台支持范围内”；
- Windows 下目录 fsync/rename write-through 的可实现性仍需实测。

Codex 接受将其列为 Windows durability/rc gate，并在 capability 被用于不可重新生成
的重要 Artifact 前评估；暂不接受把 D1 当前进程崩溃结论判错。

### D7 大 Artifact 多趟哈希和全量 read

双方事实一致：stage/commit 有多次全文件验证；`open_for_read` 全哈希，
`ArtifactReader.read_bytes` 再全量读取并校验，内存为 O(file size)。

Codex：对 D1 小 fixture 是安全优先的可接受实现；在 alpha.2 PDF/大 Artifact 前必须
提供流式读取和明确内存/大小预算。不能简单“信任 metadata”而取消内容完整性校验；
可使用一次验证后的可信句柄流式消费、校验缓存或按使用场景分层。

### D8 恢复后 available 的事件语义

Claude：消费者若只看 `artifact.committed` 会漏掉
`artifact.reconciled(state=available)`。

Codex：同意这是 D3 typed projection gate，不应让 reconciler伪造普通 committed
事件。应定义唯一的 `Artifact became available` 投影规则，覆盖正常 committed 与
恢复 reconciled(available)，并用真实 replay 测试。

### D9 partial/orphan GC 与并发

Claude：D2 并发慢 staging 可能被 grace GC 清走。

Codex：现有权威不变量明确 reconciliation 不与 commit/promote 并发，且启动时在
Workspace lock 下、reconciliation 收敛后才 ready。只要 D2 不改成后台并发扫描，
反例不可达。若未来放宽，必须引入 lease/活跃引用与竞争测试。

### D10 outbox retention

Claude：SSE 依赖 `events INNER JOIN outbox_events`；若后续 dispatcher 删除已发送
outbox，历史 replay 会丢失。

Codex：同意这是未显式锁定的 D2→D3 接口。D2 必须把 outbox 行视为 Event 发布资格
标记并至少与 Event envelope 同寿命，dispatcher 只能更新状态/次数，不能删除；
或在迁移中改成不依赖可删除 outbox 的 replay 设计。

## 5. 请求的最终收敛

请逐项返回：

1. C1～C10 的 ACCEPT / VETO / 尚未达成共识；
2. D1～D10 中是否接受 Codex 反驳；
3. 哪些是 D0/D1 本体缺陷，哪些是 D2、D3、alpha、rc 的前置 gate；
4. 是否可以保持 D0/D1 为已完成；
5. 是否允许开始 D2，以及 D2 的第一个原子工程单元必须包含什么；
6. 不得把未解决的重要异议包装成共识。
