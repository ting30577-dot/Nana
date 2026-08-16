---
title: Codex 与 Claude 对等决策记录
status: implementation-gate
date: 2026-07-29
tags:
  - nana
  - decision-log
  - codex
  - claude
---

# Codex 与 Claude 对等决策记录

## 1. 为什么需要这份记录

用户要求 Codex 与 Claude 角色平等，看到对方可审查的思考结果后共同决策。这里的
“看到思考”被落实为：

- 独立提案；
- 事实、假设和推断；
- 决策依据摘要；
- 风险、反例和备选方案；
- 对另一方的完整反驳；
- 显式接受、附条件接受或否决。

不声称任何一方能看到另一模型的隐藏 chain-of-thought。隐藏推理不可验证，也不应
成为架构证据。

## 2. 评审协议

### Round 0：共同证据包

双方读取相同材料：

- 用户目标与四项选择；
- Nana Git、代码、测试和实际 UI；
- EAI、DeepTutor、OpenScience、OpenMAIC、STORM、PaperQA2、
  MLflow/DVC/SwanLab 的官方版本演进；
- Windows first、无固定工时和废版 Vault 的事实。

### Round 1：独立提案

- Codex 在未看到 Claude 提案时完成产品、主循环、UI、架构、安全、路线；
- Claude 只收到共同证据包，独立完成提案；
- 两份提案冻结后才交换。

### Round 2：交叉反驳

Codex 读取 Claude 全文，Claude 读取 Codex 全文和 Codex 的反驳。双方必须针对
主循环、首切片、自治、可靠性、数据和技术栈逐项回应。

### Round 3：条件解除

Claude 上轮明确留下三个否决条件：

1. confidential 数据缺少合格本地模型时必须诚实降级；
2. Windows 没有强隔离后端时不得承诺未知代码无审批自治；
3. 每个 milestone 必须有 scope ceiling。

Codex 根据本机能力与官方隔离资料形成：

- 按任务 EvalPack 的本地模型白名单与明确降级；
- `builtin_local / windows_sandbox / docker` ExecutionBackend；
- 无强隔离时未知代码审批；
- 每 milestone 唯一旅程和明确不做项。

### Round 4：最终逐项会签状态

按用户隐私边界生成了脱敏会签包，只包含获准的硬件型号和必要软件版本，不包含
设备序列号、授权信息、机主名、用户名、网络标识、密钥或含用户名路径。

Claude 中转服务在初稿阶段两次、全部技术条件关闭后又一次返回空错误，没有产生
新的 D1–D10 会签文本。最后一次发送前，脱敏包针对用户名路径、序列号模式、内网
地址、MAC、密钥/授权字段做了零命中扫描。因此：

- 不能声称 Claude 已对最终文本逐项签字；
- Claude 上一轮的明确接受项仍有效；
- 三个条件是否解除由可检查规格逐条对照；
- 最终状态称为**实质性条件收敛，最终 API 会签未返回**；
- 若服务恢复，可再次只发送脱敏会签包并把结果附在本文件，不改变历史记录。

## 3. 独立提案的主要差异

| 问题 | Codex 初始判断 | Claude 初始判断 | 交叉评审结果 |
|---|---|---|---|
| 产品主循环 | 广义 Project Execution | 更偏 Paper Reproduction | Claude 条件接受 Project Execution，要求三模板证明 |
| 首切片 | 技术 runtime → 算法 → 复现 | 较早进入 PDF 复现 | Claude 接受按风险拆分，且认为优于原方案 |
| 自治 | 能力/预算内自动，越界审批 | 初始更谨慎、较多逐项审批 | 接受策略预授权，要求 Registry、隔离与预算 |
| 可靠性 | stable 前必须完成 | 初始曾推迟到后续版本 | Claude 接受纳入 `v0.3.0` |
| UI | Cockpit + Studio | 同样反对 CRUD | 共识 |
| 技术栈 | Tauri/React/TS + Python sidecar，先 spike | 相同目标，强调 fallback | 共识：Web spike → Tauri；Plan B 本地 Web |
| 数据模型 | 稳定控制平面 + 研究语义 + 派生视图 | 对象命名有差异 | 合并为统一三层 |
| Obsidian | 发布/连接路径 | 强调不能成为事务 DB | 共识 |
| confidential | 评测本地模型或降级 | 要求明确路径 | 新规格满足其解除条件 |
| Windows sandbox | backend 抽象 | 要求无隔离时诚实限制 | 新规格满足其解除条件 |

## 4. 双方共同否决的方向

- 继续在旧 PySide6 CRUD 上堆新功能；
- 把文献综述、论文聊天或刷题设为全部产品边界；
- 三种项目模式各自复制 Agent runtime；
- 首切片同时承担新桌面栈和完整 PDF 解析；
- 任意 LLM shell；
- 把 venv 当安全沙箱；
- 把 Obsidian 当事务数据库；
- 自动生成没有 locator 的“可信引用”；
- 无恢复、迁移和数据不变性就发布 stable；
- 用独立积分系统证明用户能力；
- 重写 Git/DVC/MLflow/Jupyter；
- 按对标项目短期提交速度承诺单人项目日历。

## 5. D1–D10 状态

| 决策 | 内容 | Claude 上轮状态 | 当前证据状态 |
|---|---|---|---|
| D1 | Personal Research & Engineering OS | 产品边界实质接受 | confirmed |
| D2 | Project Execution 主循环 + 三模板 | 条件接受 | 三模板映射已写入，条件满足 |
| D3 | 技术→算法→论文/仓库→优化 | 接受，优于原提案 | confirmed；真实问题实施前由用户确认 |
| D4 | Cockpit + Studio | 接受 | confirmed |
| D5 | React/TS + Python sidecar → Tauri | 接受，需 spike | implementation-gate |
| D6 | 控制平面/研究语义/派生视图 | 接受合并 | confirmed |
| D7 | 策略预授权 + 预算内自治 | 条件接受 | Registry/Budget/Approval 已形式化 |
| D8 | 数据降级 + ExecutionBackend | 上轮否决，给出解除条件 | 规格逐条满足；最终 API 会签未返回 |
| D9 | 单旅程 scope ceiling | 上轮否决，给出解除条件 | 每 milestone 已明确，条件满足 |
| D10 | stable 发布门槛 | 支持可靠性在 stable 前完成 | confirmed；最终逐项签字未返回 |

“条件满足”表示设计文本满足 Claude 明示的可检验条件，不等于伪称收到新的
`ACCEPT` 响应。

## 6. 重要共同结论

1. Nana 不押注一个尚未确定的科研领域，而先建设跨领域执行骨架；
2. 产品第一价值不是“读很多”，而是形成可验证、可复现、可复用的 Decision；
3. 能力成长是项目证据的副产品；
4. UI 必须让阅读、代码、实验、AI 活动和成果共享上下文；
5. 高自治依赖形式化能力、预算、数据策略、隔离、暂停和 Receipt；
6. 首版数据契约必须容纳失败、取消、重试、定位和恢复；
7. 多语言是有边界的工程选择，不是全面重写所有 Python；
8. 没有固定工时，就用范围上限保护项目；
9. v0.3 stable 必须通过可靠性和 Windows 交付，不是功能演示；
10. 方向确定后再做领域包，而不是现在预判。

## 7. 仍需用户参与的实施决策

这些不会改变当前产品/架构规划，但会影响具体实现：

- 确认首个真实算法调查问题；
- 选择 alpha.2 的可承受论文/仓库；
- 是否安装/启用某个强隔离后端；
- confidential Project 是否逐项目授权某个外部 Provider；
- 技术 spike 失败时是否接受本地 Web Plan B；
- v0.5 的首个领域包。

遵循用户要求：这些信息一旦会改变当期实施路径，先停下并以可选择方案询问。

## 8. 权威工作记录

仓库中保留：

- `docs/rebuild_evidence_pack.md`
- `docs/codex_independent_proposal.md`
- `docs/claude_independent_proposal.md`
- `docs/codex_cross_review_of_claude.md`
- `docs/claude_cross_review_of_codex.md`
- `docs/convergence_resolution.md`
- `docs/claude_final_review_packet_sanitized.md`

它们是本决策记录的来源，不代表所有内容都进入最终产品规格；冲突时，以本 Vault
中标记 `confirmed` 的最终文件和 [[10_完整性_可行性_可执行性终审]] 为准。
