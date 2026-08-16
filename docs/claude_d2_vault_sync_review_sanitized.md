# Nana D2 权威 Vault 11/12 同步草案（脱敏）

## 审查目标

请独立审查下列拟追加内容是否准确、无过度声明，并检查：

1. D2-00 至 D2-07 的阶段状态和证据是否完整；
2. 是否把受信 frozen worker 的窄执行面误写成通用不可信代码 sandbox；
3. 360 D2-effective、100 supplemental、23 手工 corpus、30 个真实孙进程 fixture 的分类是否诚实；
4. 是否准确保留 Workspace lock、OpenAPI/runtime app 合流、完整 prompt/log/export canary 等 D3/stable 前置义务；
5. 11 号清单映射是否避免把尚未实现的通用工具能力误标为完成；
6. 12 号证据索引是否足以让后续读者从相对路径重放审查。

请对两份追加内容分别给出 ACCEPT、VETO 或“尚未达成共识”，列出必须修改项和非阻塞建议。

## 拟追加到 11 号执行清单

### 2026-08-01：D2-00 至 D2-07 完成并共同验收

D2 在 D0 contract kernel 与 D1 Artifact/Event/HTTP-SSE runtime 上完成了首个受信、
冻结、极窄的本地执行闭环。共同 ACCEPT 的范围严格限定为
`python.unittest.locked` frozen worker；它不是通用不可信代码 sandbox，也没有开放
HTTP mutation serving、通用 shell、任意 Python、外部 publish/export 或 React UI。

| 阶段 | 状态 | 退出证据 |
|---|---|---|
| D2-00 authorization/storage hardening | 完成，纳入最终共同 ACCEPT | capability identity/digest、registry truth、safe JSON schema、Receipt/effect audit、locator privacy、schema v2。 |
| D2-01 scheduler/cancel gate | 完成，纳入最终共同 ACCEPT | 已授权 Action 单次 claim、竞争互斥、cancel 两阶段收敛、append-only Event/outbox、schema v3。 |
| D2-02 capability ceiling contract | 完成，纳入最终共同 ACCEPT | `python.unittest.locked` 的 read/write/network/env/process/timeout/default-effect ceiling。 |
| D2-03a registry/scope preflight | 完成，纳入最终共同 ACCEPT | schema v4 full registry JSON、digest round-trip、精确 process constraint、`project:source`/`project:tests` read roots。 |
| D2-03b admission service | 完成，纳入最终共同 ACCEPT | PolicyGrant/Approval 原子消费、args/action hash/registry binding、授权 Event/outbox 同事务。 |
| D2-04 locked executor | 完成，纳入最终共同 ACCEPT | 空环境、固定 argv/schema、audit guard、timeout/output/Receipt、Windows suspended-create→Job-bind→resume、真实孙进程 cancel。 |
| D2-05 runtime budget accounting | 完成，纳入最终共同 ACCEPT | schema v5 ledger、claim 前 reservation、Receipt usage 累计、runner/cancel/orphaned 保守结算。 |
| D2-06 security corpus gate | 完成，纳入最终共同 ACCEPT | 23 项手工 corpus；360 个 D2-effective + 100 个 supplemental；30 个真实孙进程 fixture；未授权 T3/T4/T4-like 通过数为 0。 |
| D2-07 D3 handoff | 完成，最终共同 ACCEPT | schema v6 append-only authorization snapshot、`D2RuntimeHandoff` v3、replay fixture、D3 消费边界。 |

对前文清单的同步判定：local scheduler、locked Python unittest、D2 窄执行面的
capability/schema/path/network/env/process/timeout/output、Run Budget、PolicyGrant、
Approval、Receipt、cancel race、child timeout、Approval 变化/过期/replay、越界路径、
shell metacharacter、未授权网络、输出上限和 Action replay 已有机器证据。通用项目文件
读取工具、scratch Artifact 写入、locked benchmark、Git 只读、公共网页读取、T3 导出、
完整 prompt/log/export canary、Provider 不可用、磁盘耗尽、通用 pause/resume 和 UI E2E
仍未完成，不因 D2 退出而自动勾选。

最终复验：聚焦回归 68/68；全量 269/269；以下七个 D2 测试模块共 55 tests 在
ResourceWarning-as-error 下通过：capability admission、run scheduler、locked executor、
budget accounting、security corpus、security matrices、runtime handoff。Python
compileall、TypeScript `tsc --noEmit`、
evidence manifest 和隐私扫描全部通过。全量 suite 的既有 shutdown ResourceWarning
已隔离到迁移期 PySide6 UI smoke，不涉及 D2 Job、pipe 或 process handle。

D3 在开放真实 mutation serving 前仍必须完成 OS 级 Workspace lock、先持锁再可写打开
SQLite、reconciliation 后才 ready、第二实例失败关闭、SQLite close 后再释放 lock，
并单独完成 OpenAPI/runtime app 合流。D3 只能消费 D2 的 Action/Event/Receipt/outbox/
Artifact projection 与 authorization snapshot，不得重新推导授权或绕过 admission、
scheduler、executor。

## 拟追加到 12 号证据索引

## 17. `v0.3.0-dev` D2-00 至 D2-07 安全执行闭环证据

| 字段 | 证据 |
|---|---|
| 执行日期 | 2026-07-30 至 2026-08-01 |
| 最终范围 | 受信 `python.unittest.locked` frozen worker 的窄执行面；不是通用 sandbox |
| schema 演进 | v2 authorization/receipt；v3 scheduler event；v4 full registry；v5 budget ledger；v6 append-only authorization snapshot |
| 最终共同结论 | Codex ACCEPT；Claude 二次收敛复审 ACCEPT；D2-07 无剩余 D2 blocker |
| 聚焦回归 | 68/68 |
| 全量回归 | 269/269 |
| 严格警告回归 | capability admission、run scheduler、locked executor、budget accounting、security corpus、security matrices、runtime handoff 七模块共 55/55，ResourceWarning-as-error |
| 安全门 | 23 手工 corpus；460 个执行场景，其中 360 D2-effective、100 supplemental；360 中的 30 个 cancel/process-tree 场景就是同一组 30 个真实孙进程 fixture，并非另外再加 30；在 corpus/matrices 覆盖面内未授权高风险通过数 0 |
| 编译/类型 | Python compileall 通过；TypeScript `tsc --noEmit` 通过 |
| 证据完整性 | 独立 D2 manifest 文件逐项 SHA-256 匹配；manifest digest 为 `1cbb07d25a1333e0a860182f0a47f915601c90af083b6e8b9daf4ec5aedd7f5d` |

### 17.1 阶段证据索引

| 阶段 | 关键证据 | 主要文件 |
|---|---|---|
| D2-00 | Registry 为授权真相；safe schema；Receipt/effect 与 locator 隐私；schema v2；本阶段有意以 decision record 作为退出摘要，不另造重复 summary | `docs/d2_00_decision_record.md`、contracts/storage tests |
| D2-01 | scheduler claim/cancel race、append-only Event/outbox、count gate | `docs/evidence/v0.3.0-dev-d2-01-summary.md`、`tests/test_d2_run_scheduler.py` |
| D2-02 | 完整 execution ceiling 与首个 built-in capability | `docs/evidence/v0.3.0-dev-d2-02-summary.md`、contract tests |
| D2-03a | full registry JSON、v4→v6 digest 不漂移、read/process scope | `docs/evidence/v0.3.0-dev-d2-03a-summary.md`、contract/storage tests |
| D2-03b | Grant/Approval 原子 consumption 与 durable authorization material | `docs/evidence/v0.3.0-dev-d2-03b-summary.md`、`tests/test_d2_capability_admission.py` |
| D2-04 | locked executor、runtime scope、Receipt、Windows Job 与真实进程树 | `docs/evidence/v0.3.0-dev-d2-04-summary.md`、executor/security tests |
| D2-05 | Run budget ledger、reservation 与 conservative usage | `docs/evidence/v0.3.0-dev-d2-05-summary.md`、budget tests |
| D2-06 | 固定 corpus 与定量矩阵，精确 reason family | `docs/evidence/v0.3.0-dev-d2-06-summary.md`、security fixtures/tests |
| D2-07 | handoff v3、schema v6、replay 与 D3 边界 | `docs/evidence/v0.3.0-dev-d2-07-summary.md`、`docs/d2_runtime_handoff.md`、handoff fixture/test |

### 17.2 关键反驳、VETO 与修复证据

最终审查不是一次性通过。Codex 完整扫描后 VETO 旧退出结论；Claude 首审又给出
Popen 后绑定 Job 的逃逸窗口和 security matrix 有效性反例。最终修复包括：

1. Claude F6 的 Windows Job 反例：worker 改为 `CREATE_SUSPENDED -> AssignProcessToJobObject -> ResumeThread`；
2. 30/30 fixture 启动真实父进程和真实孙进程，并在 5 秒内验证整树退出；
3. 460 个执行场景重新分类为 360 D2-effective 与 100 supplemental，后者不冒充
   prompt runtime gate；
4. args Artifact 在 admission/executor 双入口校验 persisted size 和授权 artifact budget；
5. orphaned Action 写 Receipt、记录保守 usage、释放已结算 reservation，Run quarantine；
6. worker 使用 `-B`，observed effects 明确只是 advisory audit evidence；
7. Claude F10 的 durable registry/digest 证据链：built-in registry digest 固定，v4 数据
   经 v5/v6 migration 后 bit-for-bit 不漂移。首审接受 full registry truth，二审只复核
   同一 F10 的 digest 稳定性补证；它不是另一条 Job issue。

Claude 首审接受 F2/F3/F9/F10/F11，对 F1/F4/F5/F7 给出条件性接受，对 F6/F8
保留异议；二审接受 F1/F4/F5/F6/F7/F8，并确认 F10 的 digest 补证。最终 D2-07
共同 ACCEPT，且没有剩余 D2 blocker。

### 17.3 结论边界与后续义务

当前零越权结论只覆盖受信 frozen worker 的既有窄执行面。460 个执行场景分解为：
200 路径/参数、50 credential canary、50 Approval/Grant、30 真实 cancel/process-tree
和 30 malicious/oversized Artifact，共 360 个 D2-effective；另有 100 个 prompt-like args
containment，明确是 supplemental 且不计入 360。50 个 canary 属于 360，只覆盖当前
实际存在的 child env/stdout/stderr 边界，不代表完整 Prompt/log/export canary gate。
30 个 cancel/process-tree 场景就是同一组 30 个真实孙进程 fixture，不是两组各 30。
完整 Prompt/log/
export runtime gate、hostile-code sandbox、更深 process tree/breakaway、orphaned 全局资源
监控仍属于 stable/后续加固。

D3 可先建设只读 UI 或 replay fixture viewer；真实 mutation serving 前必须关闭
Workspace lock 生命周期和第二实例/ready-order 测试，并完成 OpenAPI/runtime app 合流。
D3 不得重新查询 PolicyGrant/Approval 推导授权，不得绕过 D2 admission/scheduler/executor，
也不得把 UI local state 当作 canonical truth。

证据强度边界：上述 SHA-256、55/55、68/68 与 269/269 由 Codex 在本地工作区复算/
重跑；Claude 使用脱敏 manifest、fixture 和输出摘要完成只读静态一致性审查，不能在
其服务端重跑本地测试。第三方应以 D2 manifest、对应 `.sha256` 和列出的测试命令
自行复算，不以 Vault 的转述替代原始文件。

### 17.4 可重放证据入口

- 最终退出审查：`docs/d2_07_exit_review.md`；
- 最终共同决策：`docs/d2_07_decision_record.md`；
- Claude 收敛响应：`docs/claude_d2_convergence_response_sanitized.md`；
- D3 handoff：`docs/d2_runtime_handoff.md`；
- replay fixture：`fixtures/v0.3.0-dev/d2_runtime_handoff_replay.json`；
- security corpus/matrix：`fixtures/v0.3.0-dev/d2_security_corpus.json` 与
  `fixtures/v0.3.0-dev/d2_security_matrices.json`；
- evidence manifest：`docs/evidence/v0.3.0-dev-d2-manifest.txt` 与对应 `.sha256`。

历史 `d0` manifest 路径继续保留，但本节只把自解释的 D2 manifest 作为 D2 退出证据入口。
