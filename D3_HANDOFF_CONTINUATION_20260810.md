# Nana v0.3.0-dev-D3：完整连续开发交接（2026-08-10）

> 这是给“没有任何旧对话记忆”的新 Codex 对话使用的完整交接。读取本文件后，必须继续实际开发 Nana D3，直到 D3 的验收目标完成；不能把任务缩减为只做审查、只给建议或只等待用户转发消息。

## 0. 当前最高优先级与协作边界

### 0.1 当前任务

继续 `C:\Users\q1968\Desktop\Nana` 工作区中的 Nana 项目 `v0.3.0-dev-D3` 开发。

D3 的核心目标是：把 D2 已经证明的真实执行事实安全地投影到最小 React E2E 纵向切片，让用户能通过界面理解并完成 dev 旅程。D3 不是“先做漂亮 UI”，也不是让前端重新发明授权或执行语义。

目标纵向旅程：

`create → provenance → editable Plan → locked T2 test Run → Activity → Artifact → Finding draft → one-time Approval → controlled T3 draft export → Receipt`

### 0.2 不再调用 Claude

用户已经明确要求：暂时不再调用 Claude，不再运行 `scripts/ask_claude.py`，不再重试中转、不再等待 Claude，也不要求用户充当中转员。

历史上用户曾手工转达 Claude 的截图审查结果；这些结果在本文件中保留为“历史独立审查输入”，不得伪装成新的自动审查，也不得据此声称当前已经获得 Claude ACCEPT。

### 0.3 原始共同审查闸门与当前治理决策

原项目规则要求重要决策由 Codex 与 Claude 共同设计/审查，并明确记录 `ACCEPT`、`VETO` 或“尚未达成共识”。当前机器闸门仍反映原规则：

- `joint_status = "unresolved"`
- `implementation_authorized = false`
- `capability_registered = false`
- `filesystem_write_authorized = false`

因此，不能偷偷把这些值改成 true，也不能把 D3-07 称为已完成。

用户现在已决定不再需要 Claude，但尚未在本文件生成时自动替用户改变项目治理规则。新对话开始后必须先记录一个明确的本地治理决策：

1. **保留原始共同闸门**：则 D3-07 的真实实现闸门继续 unresolved，允许做安全的前置实现/证据工作，但不得开放受闸门保护的真实 mutation serving；或
2. **改为 Codex-only 本地闸门**：必须在项目文档/决策记录中明确记录这是用户授权的治理变更、原因是 Claude 中转不可用且不再使用，并保留全部不变量、证据要求和 fail-closed 约束；只有记录完成、测试完成后才能按本文件实施 D3-07。

不得以“Claude 无法连接”为理由无记录地放宽安全边界。

## 1. 新对话启动时必须读取的文件

### 1.1 工作区规则

- `AGENTS.md`
- `docs/claude_collaboration.md`（只为理解历史协作/脱敏边界；不要因此重新调用 Claude）

### 1.2 权威规格（位于 Obsidian Vault）

开始任何 D3 实现前，完整阅读：

- `D:\Obsidian Vault\Nana_研究系统\00_Nana_总览与导航.md`
- `D:\Obsidian Vault\Nana_研究系统\05_技术架构与数据契约.md`
- `D:\Obsidian Vault\Nana_研究系统\06_AI自治_安全与隐私.md`
- `D:\Obsidian Vault\Nana_研究系统\07_版本路线图与验收门槛.md`
- `D:\Obsidian Vault\Nana_研究系统\10_完整性_可行性_可执行性终审.md`
- `D:\Obsidian Vault\Nana_研究系统\11_首个纵向切片执行清单.md`
- `D:\Obsidian Vault\Nana_研究系统\12_验证记录与证据索引.md`

### 1.3 D2→D3 交接资料

- `docs/d2_runtime_handoff.md`
- `docs/d2_07_exit_review.md`
- `docs/d2_07_decision_record.md`
- `docs/evidence/v0.3.0-dev-d2-manifest.txt`
- `docs/evidence/v0.3.0-dev-d2-manifest.sha256`
- `fixtures/v0.3.0-dev/d2_runtime_handoff_replay.json`
- `fixtures/v0.3.0-dev/d2_security_matrices.json`

### 1.4 当前 D3 交接、闸门和证据

- `D3_HANDOFF_START_HERE.md`
- 本文件 `D3_HANDOFF_CONTINUATION_20260810.md`
- `docs/evidence/v0.3.0-dev-d3-07-gate-decision.json`
- `docs/evidence/v0.3.0-dev-d3-local-regression-and-manifest-refresh-20260810.md`
- `docs/evidence/v0.3.0-dev-d3-authority-sync-summary.md`
- `docs/evidence/v0.3.0-dev-d3-06-manifest.txt`
- `docs/evidence/v0.3.0-dev-d3-06-manifest.sha256`
- `docs/claude_d3_06_implementation_exit_packet_sanitized.md`（历史手工审查输入）
- `docs/claude_d3_07_entry_gate_packet_sanitized.md`（历史手工审查输入）

开始工作前先检查 `git status --short` 和相关 diff。不得运行 `git reset`、`git checkout`、`git clean`，不得删除或覆盖与本任务无关的现有用户文件。

## 2. D0、D1、D2 已完成事实

- D0 已完成。
- D1 已完成。
- D2 技术完成度：`ACCEPT`。
- D2 官方证据/签核：`ACCEPT`。
- D2→D3 衔接：`ACCEPT`，附 Workspace lock 等硬门。

D2 最终验证：

- `compileall nana_sidecar tests scripts`：通过
- `npm run check`：通过
- D0 manifest 自检：通过
- 全量 Python unittest：当时 `269 tests OK`
- D2 七模块 `ResourceWarning-as-error`：`55 tests OK`
- D2 security matrix + runtime handoff：`14 tests OK`
- D2 manifest：`102` 条目，`0` hash 错误
- D2 manifest digest：`1cbb07d25a1333e0a860182f0a47f915601c90af083b6e8b9daf4ec5aedd7f5d`

### 2.1 D2 的真实范围（不得扩大解释）

D2 只证明受信、冻结、极窄的 `python.unittest.locked` 本地执行闭环。它不是通用 hostile-code sandbox；没有开放 HTTP mutation serving；没有实现 React UI；没有实现外部 publish/export；没有允许任意 shell 或任意 Python 执行；没有完成完整 prompt/log/export canary stable gate。

### 2.2 D2 交给 D3 的事实源

D3 消费以下 canonical facts，不重新发明它们：

`actions`, `events`, `outbox_events`, `action_receipts`, `action_authorizations`, `artifacts`, `runs`

另有 D2 runtime handoff fixture、structured errors、Event replay / Artifact projection / Receipt semantics。

### 2.3 D3 绝对不能做的事

- 不得重新查询 `PolicyGrant` / `Approval` 来自己推导授权。
- 不得绕过 D2 admission / scheduler / executor。
- 不得把 UI local state 当 canonical truth。
- 不得在 Workspace lock 完成前开放真实 mutation serving。
- 不得把 `python.unittest.locked` 的安全结论泛化成通用 sandbox。
- 不得偷偷把旧 OpenAPI/runtime app 合流混入无关改动。

## 3. D3 硬门和产品边界

在真实 mutation serving 前必须实现并测试 Workspace lock 生命周期：

1. 写 SQLite 前先取得 OS 级 Workspace lock。
2. reconciliation 完成后才报告 ready。
3. 第二实例必须 fail closed。
4. SQLite close 后才释放 lock。
5. launcher/sidecar 崩溃恢复必须测试。

其他硬门：

- OpenAPI/runtime app 合流是 D3 显式决策，不能隐式合流。
- 浏览器 SSE 客户端必须使用 `fetch + ReadableStream`，不能使用原生 `EventSource`，因为需要附加 `Authorization` header。
- D3 runtime HTTP 路由保持默认拒绝策略；新增公共/bootstrap route 必须单独安全审查。
- UI 只能展示 D2 事实状态，例如 `authorization pending`、`running`、`cancelled`、`effect_unknown`、`Receipt`；不得前端臆造成功状态。
- 全量测试退出时已有的 PySide6 shutdown `ResourceWarning` 不阻断 D3 起步，但在开放真实写服务前必须确认它不涉及 D3 handle/process/write path。

## 4. D3 阶段状态（不要误报）

- D3-00：已接受。
- D3-01：已接受。
- D3-02：已接受。
- D3-03：已接受。
- D3-04：已接受。
- D3-05：已接受。
- D3-06：**未完成共同 ACCEPT**。Codex 本地实现和回归当前通过，但历史独立审查结论是 `NOT YET CONSENSUS`，不是 ACCEPT，也不是 VETO；存在证据缺口 F-A～F-E，见第 5 节。
- D3-07：**未开始实现，未授权完成**。当前只有冻结设计/entry gate；历史独立安全审查结论 `NOT YET CONSENSUS`，见第 6 节。
- D3-08A、D3-08B、D3-09：已有规划/衔接，但必须等 D3-07 完成后再按清单推进，不要越过 D3-07 偷跑。

## 5. D3-06 当前未完成项：实现证据补强

### 5.1 历史审查结论

用户手工转达的 Claude D3-06 审查读取了 `docs/claude_d3_06_implementation_exit_packet_sanitized.md`（144 行），结论为：

`NOT YET CONSENSUS`

这表示证据不足，不能 ACCEPT；它没有给出 VETO。新对话不需要、也不得重新调用 Claude，但必须处理这些缺口或在本地决策记录中说明为何仍不能关闭。

### 5.2 已被认为合理的设计/声明

- 范围冻结为 `python.unittest.locked`，明确排除 Approval、T3 export、任意 shell/Python、网络和 hostile-code sandbox。
- D3-07 仍被 gate 阻止。
- worker 只获得冻结的 D2 进程、不可变 test ID/root/limits 和线程安全 cancel callback，不获得 SQLite connection 或 database write handle。
- `to_canonical_command` 由服务端注入 `PYTHON_UNittest_LOCKED_CAPABILITY`。
- D2 admission、durable authorization、scheduler claim、budget reservation 均在 owner lane；billing basis 采用 `measured_observed_effect`、`not_charged_pre_spawn`、`conservative_uncertain_effect`；uncertain effects 不得被静默算作成功或退款。
- 声明了 `BEGIN IMMEDIATE`、七步事务边界、重启状态矩阵和 atomic terminal facts。

### 5.3 必须补强的证据

**F-A（P1，证据不足）**：packet 主要是叙述和 pass 计数（例如 `17 / 51 / 107 / 55 / 372`），没有可独立核验的代码/diff/日志；“final no-edit scan”是自我声明，无法独立确认 F-14～F-32 或第 10 点已闭合。

解除方向：提供本地可复现测试/日志和关键实现证据，至少覆盖 `to_canonical_command`、target/fixture 拒绝、`BEGIN IMMEDIATE`、worker 构造、restart reconciliation。证据必须落入项目文件并可由命令重跑。

**F-B（P1）**：`StartRunRequest` 有 `command` 与 `target` 字段；只说后端拒绝非法 target/revision/fixture，但没有证明精确的服务端 allowlist。

解除方向：负向测试证明 target 是服务端拥有的精确固定目标/注入 fixture，不允许任意路径或任意 fixture；测试必须在 Artifact provisioning 之前拒绝。

**F-C（P2）**：packet 没有明确证明运行时不会重新查询/推导 `PolicyGrant` / `Approval`。

解除方向：测试或只读代码证据证明 D3-06 唯一授权来源是 D2 admission record，运行时不重新查询、不由用户/浏览器推导授权。

**F-D（P2）**：有 transaction rollback 叙述，但没有明确“blob 提升后、commit 前 crash → 下次恢复/回收 orphan、无重复计费、无幻觉 Receipt”的专门用例。

解除方向：加入 crash/restart/orphan/recovery 测试，证明 Receipt 和 effect 只出现一次且状态不被伪造。

**F-E（P3）**：提到了 `effect_unknown`、`orphaned`、`termination_failed`、conservative，但没有明确 `unknown_pending` 的分类和终态映射。

解除方向：明确分类表和测试，残留不可验证必须进入保守终态，不能显示为 failed 或 success。

补强时不能扩大 D2 能力范围，也不能提前打开 D3-07 capability。

## 6. D3-07 当前未完成项：设计已冻结，安全实现证据缺失

### 6.1 历史审查结论

用户手工转达的 Claude D3-07 entry/security gate 审查只读取 `docs/claude_d3_07_entry_gate_packet_sanitized.md`，明确把其他引用文件视为 `design-only / planning-only`，结论为：

`NOT YET CONSENSUS`

不是 ACCEPT，也不是 VETO。不能实现后再补闸门，也不能因为 Claude 不再接入就自动跳过。

### 6.2 已冻结的设计要点

1. approved 单事务闭合六项：decision、Action authorization、一次性 consumption、Approval/Action Event/outbox、command result、全部置入同一 owner-lane 事务。
2. denied/expired/changed/replay 永不授权。
3. 不提供 public `ConsumeApproval`。
4. Export Run/Action 独立，并带 canonical provenance。
5. T3 capability 严格为 `export.draft_external`，`grantable=false`、一次性；浏览器不能选择 capability。
6. opaque selection 绑定 LocalSession、60min、一次性、重启收敛。
7. 外部目标只能是既有专用 fixed-local 空目录。
8. 拒绝 root/system/Nana/Workspace/reparse/alias/UNC/network/cloud/collision/changed。
9. durable first-write fence 先于 probe/任何外部字节。
10. unsupported atomic replace fail-closed，无 fallback/retry/rebind。
11. 对 failed/effect_unknown/cleanup/crash/restart/compensation 分类。
12. report 只允许 server-derived canonical public 输入。
13. Receipt/before-after/hash/idempotency/effect 闭合必须有实现证据。
14. 缺失 implementation safety evidence 是严重阻塞。

### 6.3 F1～F9 必须关闭的缺口

**F1（Blocker）**：D3-06 独立 exit unresolved，机器标志仍为 false；不能注册或开放 export capability。

**F2（Blocker）**：transaction map、contract、test matrix、selection registry 都只是 design-only；缺少独立可复现实现证据。

**F3（High）**：SQLite transaction/savepoint 语义未证明。需要 private in-transaction primitive；approved 路径必须是 `BEGIN…COMMIT`，不能嵌套 command transaction；失败整体回滚；denied 路径不得写 authorization/consumption。

**F4（High）**：一次性 consumption/replay 只有声明，没有并发测试。必须证明一个 Action 只能 authorize/consume 一次，重复 approval/replay 被拒绝且无副作用。

**F5（Medium-High）**：cloud-sync denylist 可能只覆盖已知根目录，无法证明任意 OneDrive/第三方同步目录均拒绝。必须采用实际 fixed-root/显式约束；best-effort 不能算安全。

**F6（Medium）**：atomic replace 支持、probe、清理和跨文件系统失败分类没有实现证据。需要支持的 filesystem 矩阵；probe/cleanup 失败必须进入 fail/effect_unknown，不污染成功状态。

**F7（Medium-High）**：post-write crash/restart/compensation 矩阵未证明。需要 `reserve → commit → finalize` 恢复测试、重启状态、恰好一个 Receipt/effect、禁止 retry/rebind。

**F8（Low-Medium）**：before/after evidence 和 canary 不充分。必须有确定性 canary；render/report 时重新 hash snapshot；不能只测“没有 credential-canary match”。

**F9（Low）**：provenance 依赖 Export Run/source snapshot hash；生成 report 时必须再次检查 snapshot hash，防止 stale/mismatch。

## 7. D3-07 实现时不可放松的十条约束

1. approved 路径必须是一条 `BEGIN…COMMIT`；denied 路径不得写 authorization/consumption。
2. 永远不暴露 public `ConsumeApproval`。
3. Approval subject 必须是 Action ID/hash；changed、expired、denied、replay 永不授权。
4. capability 严格是 `export.draft_external`，一次性，浏览器不能选择 capability、authorization 或 path。
5. durable first-write fence 必须先于 probe/任何外部字节。
6. unsupported/unverifiable filesystem fail-closed；不允许 non-atomic fallback、retry、target rebinding。
7. 拒绝 root/system/Nana/Workspace/reparse/alias/UNC/network/cloud/collision/changed；固定 filename 并进行 handle identity recheck。
8. report 只接受 server-derived canonical public input；执行 escaping、NFC、LF、UTF-8、canary 检查，并在 render 时重新检查 snapshot hash。
9. raw path、directory handle、volume identity、opaque token 只存在进程内；持久记录只保存 non-locating commitment/expiry/subject/binding/version；重启永不 rebind。
10. 残余不可验证必须是 `effect_unknown`，本地永远不能把它当 failed 或 success。

## 8. 当前机器闸门和证据索引

文件：`docs/evidence/v0.3.0-dev-d3-07-gate-decision.json`

当前精确状态：

```text
joint_status: unresolved
implementation_authorized: false
capability_registered: false
filesystem_write_authorized: false
source_records: 44
```

所有 source record 当前都存在。不要只改 JSON 标志；任何闸门变更都必须同时有决策记录、实现证据、测试证据和 manifest/hash 同步。

D3-06 manifest 当前：

```text
entries: 23
hash errors: 0
digest: 0b4c0c25f6522c2ded42063022ebd6205684347b832730938b8bb258a851de5c
```

每个 D3 子阶段结束后都要更新权威证据或准备可同步的证据摘要，避免再次出现“代码通过但权威索引未登记”的断链。

## 9. 当前已做的本地改动/验证（不要重复误判为未做）

当前工作区已经有以下 D3 防线/证据更新：

- `nana_web/src/sse.ts`：SSE parser 拒绝空的 `aggregate_type`、`aggregate_id`、`occurred_at`。
- `nana_web/src/sse.test.ts`：malformed envelope 测试。
- `tests/test_d3_runtime_authority.py`：bootstrap page-token 跨 session 拒绝；future forbidden command types 在任何 `command_log` 写入前返回 422。
- `tests/test_d3_07_pre_gate_guard.py`：闸门仍为 false；curated journey command names 不含未来禁止命令；生产 UI 不使用 `EventSource`；当前 T2 capability ceiling；记录“当前不调用 Claude”的连续边界。
- `D3_HANDOFF_START_HERE.md`：已更新到 2026-08-10 快照、当前计数和 no-Claude continuation boundary。
- `docs/evidence/v0.3.0-dev-d3-06-manifest.txt/.sha256`：已刷新到 23 entries/0 hash errors/上述 digest。
- `docs/evidence/v0.3.0-dev-d3-local-regression-and-manifest-refresh-20260810.md`：记录当前回归、manifest、pre-gate handoff、future command rejection 等证据。
- `docs/evidence/v0.3.0-dev-d3-authority-sync-summary.md`：当前计数和 runtime rejection 说明已同步。
- gate JSON source records 已增至 44，全部存在。

不要用 reset、checkout 或清理操作抹掉这些用户已有改动。

## 10. 最新验证基线

以下是当前已完成的最新本地验证：

```powershell
.\.venv\Scripts\python.exe -m compileall nana_sidecar tests scripts
.\.venv\Scripts\python.exe -m unittest
npm.cmd run check
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
```

结果：

- compileall：通过。
- 全量 Python unittest：`386 tests, 2 skips, OK`。
- `npm.cmd run check`：通过。
- Vitest + projection self-test：`58` 个 Vitest 测试及 projection self-test 通过。
- production build：通过。
- Playwright E2E：`17 tests, 0 retries, 0 failures`。

D3 边界严格回归命令：

```powershell
.\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest tests.test_d3_07_pre_gate_guard tests.test_d3_06_journey_runtime tests.test_d3_journey_commands tests.test_d3_journey_runtime tests.test_d3_read_models tests.test_d3_runtime_authority tests.test_d3_workspace_lock tests.test_claude_reviewer -q
```

结果：`123 tests, 2 skips, OK`。

已知环境/历史问题：

- 全量 unittest 退出时仍可能出现旧 PySide6 GC shutdown `ResourceWarning`；D3 严格边界命令通过，当前没有证据表明该 warning 涉及 D3 handle/process/write path。
- 第一次 sandboxed npm test/build 曾因 esbuild 读取父目录权限失败；在受控本地验证中通过，属于环境边界而非代码失败。若再次出现，先记录命令和环境，不要把它误报为功能回归。
- `git diff --check` 当前无 whitespace error；可能有无关文件的既有 LF/CRLF 警告。

## 11. 新对话必须执行的连续开发路线

### 阶段 A：启动和事实复核

1. 读取本文件、`AGENTS.md`、权威规格、D2 交接和当前 D3 evidence。
2. 检查 `git status --short`、gate JSON、manifest/hash 和相关测试。
3. 运行最小基线（compileall、D3 strict boundary、npm check）；必要时再跑全量。
4. 不调用 Claude，不修改闸门标志。

### 阶段 B：先处理 D3-06 未闭合证据

保持 `python.unittest.locked` 极窄范围，补充 F-A～F-E 的本地可复现证据：

- target/fixture 的服务端 allowlist 与负向拒绝；
- `to_canonical_command` 的服务端 capability 注入；
- admission record 是唯一授权来源，运行时不重查/不推导；
- BEGIN IMMEDIATE/worker 构造/SQLite handle 隔离；
- blob promotion 后 commit 前 crash、orphan recovery、无重复计费、无幻觉 Receipt；
- `unknown_pending` 等残余状态的明确分类和 conservative terminal mapping。

每项都要有代码、测试、运行输出或只读证据；更新 D3-06 evidence/manifest，不要只改叙述性 packet。

### 阶段 C：明确治理路径

在项目决策记录中选择并写明“保留 joint gate”或“用户授权改为 Codex-only gate”。

- 若保留 joint gate：继续做安全前置工作，但 D3-07 implementation authorization 保持 false。
- 若改 Codex-only：记录用户授权、原因、范围、不可放松的不变量和独立验收要求，然后仍必须完成第 6、7 节所有实现证据；不能把“没有 Claude”当作“免审查”。

### 阶段 D：在合法授权后分小步实现 D3-07

建议顺序（每步都测试并更新证据）：

1. `07-01`：Approval six-item owner-lane transaction，单 `BEGIN…COMMIT`，denied/expired/changed/replay 负向路径。
2. `07-02`：严格 `export.draft_external` capability 注册/一次性消费和 server-side injection；浏览器不可选 capability/auth/path。
3. `07-03`：LocalSession opaque selection、固定专用 empty target、root/system/Nana/Workspace/reparse/alias/UNC/network/cloud/collision/changed 拒绝、first-write fence、atomic replace 支持矩阵。
4. `07-04`：Export Run/Action canonical provenance、before/after/hash/canary、Receipt、effect_unknown/orphan/cleanup/crash/restart/compensation 矩阵及 snapshot recheck。
5. `07-05`：实现审查、全量负向/并发/崩溃恢复测试、证据摘要、manifest/hash、gate decision 更新。

实现期间严禁把 OpenAPI/runtime app、任意 shell/Python、网络或 hostile sandbox 混入 D3-07。

### 阶段 E：完成 D3-08A、D3-08B、D3-09

只有 D3-07 的实现、证据和闸门正式完成后，才继续后续阶段。按照现有路线图逐项推进，保持 UI 只读投影 D2 facts，真实写服务必须经过 Workspace lock/reconciliation/second-instance/crash recovery 全套证明。

D3 最终完成必须包含：

- 用户可以通过 React E2E 完成目标纵向旅程；
- UI 显示的状态全部来自 canonical facts/projection/replay，不是 local optimistic truth；
- T2 Run、Approval、T3 draft export、Receipt 和失败/不确定状态均有可复现证据；
- Workspace lock 和 runtime default-deny 等硬门通过；
- 权威 evidence index、manifest 和 digest 已同步；
- 最终 decision 明确为 ACCEPT（或明确列出尚未达成共识/阻塞，绝不伪造完成）。

## 12. 交接给新对话的首条指令（可直接复制）

```text
你正在 C:\Users\q1968\Desktop\Nana 继续 Nana v0.3.0-dev-D3。请先完整阅读 D3_HANDOFF_CONTINUATION_20260810.md、AGENTS.md、其中列出的 7 个权威 Vault 规格、D2 交接文件和当前 evidence。不要调用 Claude，不要运行 ask_claude.py，不要等待中转。此文件是连续开发交接，不是只读审查任务：请从“阶段 A 启动和事实复核”开始，继续处理 D3-06 F-A～F-E 证据缺口；随后根据明确记录的治理决策推进或保持 D3-07 闸门；在合法授权后按 07-01～07-05 实际实现、测试、同步权威证据，并继续 D3-08A/B/09，直到 D3 完成。不得 reset、checkout、clean 或删除无关文件；不得绕过 D2 admission/scheduler/executor；不得在 Workspace lock 完成前开放真实 mutation serving；不得把 python.unittest.locked 泛化为 hostile sandbox；不得把 UI local state 当 canonical truth。每个阶段完成时报告代码、测试、证据、闸门状态和下一步，不要只给审核意见。
```

## 13. 交接完成判定

新对话只有在完成 D3 的真实实现、E2E 纵向旅程、Workspace lock/runtime safety、失败/重启/Receipt 语义和权威证据同步后，才能说“D3 完成”。

在此之前，最准确的状态是：

```text
D0 ACCEPT
D1 ACCEPT
D2 ACCEPT
D3-00..05 ACCEPT
D3-06 implementation locally regressed but evidence consensus unresolved
D3-07 design frozen, implementation not authorized, consensus unresolved
D3-08A/B/09 pending D3-07
Claude calls: explicitly disabled by user
Next dialogue responsibility: continue implementation to D3 completion
```

