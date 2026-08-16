# Codex 独立提案：Nana Research & Engineering OS

> 形成时间：2026-07-29  
> 输入：仅使用 `rebuild_evidence_pack.md` 和 Nana 代码/实机基线。  
> 状态：独立提案，尚未阅读 Claude 的本轮提案，不代表共同结论。

## 1. 产品定义

**Nana 是面向未来算法工程师的本地优先、自主执行、证据可追溯的个人科研与工程
操作系统。它把一个真实问题连续推进为可验证的知识、可复现的实验、可复用的
工程资产和可证明的个人能力。**

不把“科研模式”和“成长模式”建设成两套产品。唯一主循环是：

```text
目标/问题
→ 调研与证据
→ 假设/方案
→ 实现与实验
→ 比较与反驳
→ 决策/成果
→ 跨项目复用
```

个人成长是这条主循环的派生结果：系统从用户真正理解、实现、调试、复现和迁移
过的工作中生成“能力证据”，而不是建立另一套打卡、积分或 AI 评分体系。

## 2. 关键产品原则

1. 项目而非论文、聊天或知识库是一级入口；
2. Artifact 而非表单记录是长期资产；
3. Run 是不可变事实，Finding/Decision 是可修订解释；
4. AI 默认执行，用户可以随时观察、暂停、转向、撤销；
5. 每个重要结论能回到来源、代码、数据或运行；
6. 公共资料可使用云模型，私密资料默认不离开本机；
7. Obsidian 是可连接和导出的个人知识库，不是 Nana 唯一的事务数据库；
8. 不自研已有成熟工具：Git、DVC、MLflow/SwanLab、Jupyter、容器和语言服务
   通过适配层接入。

## 3. 双层界面

### 3.1 Research Cockpit

启动后不是空聊天框，也不是对象列表，而是：

- 当前目标与最近项目；
- 等待用户终审、失败、超预算或需要权限的 Agent Run；
- 正在运行/可恢复的实验；
- 本周形成的 Findings、Decisions 和可复用 Artifacts；
- 基于真实工作证据派生的能力变化与薄弱环节；
- 全局捕获入口：问题、网址、论文、仓库、本地文件、数据集。

### 3.2 Research Studio

进入项目后采用 IDE 式布局：

```text
┌ 项目/资料/产物树 ┬ 阅读器 / 编辑器 / Notebook / 可视化 ┬ AI 活动与证据检查器 ┐
│ Inquiry          │ 多标签中心工作区                      │ Plan / Actions       │
│ Sources          │ PDF、Markdown、代码、Diff、图表       │ Evidence / Cost      │
│ Code & Data      │                                      │ Pause / Steer / Undo │
│ Runs & Findings  ├───────────────────────────────────────┴────────────────────┤
│ Decisions        │ 终端 / Run 日志 / 指标 / 测试 / 问题面板                    │
└──────────────────┴───────────────────────────────────────────────────────────┘
```

关键交互：

- Command Palette 和全局搜索；
- 选择原文即可生成 Evidence，保留页码/文件/行号/commit；
- AI 计划先作为可编辑任务图展示，高风险步骤才出现审批；
- 中心区可以在阅读、代码、实验和报告之间保持同一项目上下文；
- Focus Mode 隐藏非必要面板，驾驶舱保持安静，Studio 保持高密度；
- 所有 Agent Action 进入时间线，显示输入、工具、产物、成本、状态和撤销能力。

## 4. 数据与领域模型

当前七对象不作为不可变边界。建议两层模型：

### 4.1 稳定核心

- `Workspace`
- `Project`
- `Inquiry`：问题、目标、范围、完成标准
- `Resource`：论文、网页、仓库、数据集、本地文件
- `Artifact`：代码、Notebook、数据、图、报告、模型、导出包；内容寻址并版本化
- `Run`：Agent、脚本、测试、实验、解析任务的不可变运行记录
- `Relation`：受控类型的对象关系
- `Event`：append-only 行为与状态变更

### 4.2 研究语义

- `Claim`
- `Evidence`
- `Hypothesis`
- `Method`
- `Finding`
- `Decision`
- `CapabilityEvidence`

研究语义可以随版本增加，但稳定核心不能依赖某一研究领域。关系必须使用注册的
类型和约束，不能退化为任意知识图谱。

## 5. 技术架构

立即停止在 PySide6 页面上扩展新 UI，但保留现有版本只读可运行，先做纵向技术
切片，切片通过后再正式迁移。

建议目标栈：

- **Tauri 2 / Rust**：Windows 桌面壳、进程生命周期、Credential Manager、
  文件授权、更新和签名；
- **React + TypeScript**：驾驶舱与科研 IDE；Monaco、PDF.js、xterm.js、
  ECharts/Plotly；
- **Python 3.11+ local sidecar**：论文/仓库解析、Agent orchestration、算法/
  ML 实验、Jupyter 和科学库；
- **FastAPI + OpenAPI + SSE/WebSocket**：显式契约和可恢复事件流；
- **SQLite (WAL)**：canonical metadata、event log、审批和索引元数据；
- **内容寻址文件仓库**：原始资料、解析结果、代码快照和运行产物；
- **DuckDB/Parquet**：大规模实验分析的可选派生层；
- **容器/受限进程执行器**：Docker/Podman 可用时优先；轻量 Python 任务可用
  独立 venv + OS 资源/路径限制；
- **Git/DVC/MLflow/SwanLab 适配器**：按项目启用。

不在首版引入 Postgres、云后端、多人权限、分布式队列或自研向量数据库。

## 6. 高自治与隐私

定义四类动作：

| 等级 | 默认行为 |
| --- | --- |
| Observe | 读取已授权项目、索引、公开网络检索，自动执行 |
| Reversible Work | 在 Nana 工作区创建/修改草稿、运行受限实验，自动执行并保留 diff/receipt |
| Sensitive/External | 上传私人资料、调用会离开本机的数据、访问未授权目录、执行未知仓库代码，执行前审批 |
| Irreversible/Publish | 删除、覆盖不可恢复数据、发布、提交外部系统、支付和最终研究结论，必须审批 |

数据分级：

- `public`：公开论文、公开仓库，可路由云模型；
- `personal`：个人笔记和未公开草稿，默认仅本地；用户可逐项目授权云处理；
- `confidential`：未公开代码/数据，必须显式白名单模型与目标；
- `secret`：密钥和凭据，永不进入模型上下文。

“高自治”是少打断用户，不是取消安全边界。普通联网检索无需逐次审批；数据外发、
未知代码执行、破坏性写入和最终发布必须审批。

## 7. 版本路线

当前 `v0.2.0-alpha` 改称“冻结原型”，不继续堆功能。

### `v0.3.0-dev`：Architecture Runway

- 新 monorepo 骨架与桌面/sidecar 握手；
- Project、Artifact、Run、Event 最小模型；
- Tauri/React Studio shell；
- 旧数据库和算法模块只读导入器；
- 一键开发启动、崩溃退出和端到端 smoke。

退出门槛：Windows 新壳可启动，创建项目、写入 Artifact、运行一个 Python 测试、
实时看到事件并重启恢复。

### `v0.3.0-alpha.1`：Algorithm Investigation Slice

使用“负数为何破坏可变滑窗、如何用前缀和+单调队列解决”完成：

- 导入公开资料和 Nana 代码；
- AI 建计划、查证、修改代码、运行正常/边界/反例；
- Evidence 与文件/行号绑定；
- 生成 Run、Finding、Decision 和可复用实现；
- 用户只在未知代码执行和最终 Decision 审批。

### `v0.3.0-alpha.2`：Paper/Repo Reproduction Slice

- PDF/仓库版本化导入；
- 页码/commit/symbol 证据；
- 环境锁定、baseline、指标和产物比较；
- 失败恢复、暂停/继续、预算和上下文压缩。

### `v0.3.0-beta`

- 驾驶舱、全局捕获、AI Run Inbox；
- 三个真实项目连续使用；
- 数据迁移、备份恢复、离线降级、凭据和 sandbox 安全测试；
- Obsidian 连接/导出。

### `v0.3.0`

三个验收场景全部可重复完成，连续使用四周没有 P0 数据问题，所有结论可回溯，
安装/升级/卸载不损坏用户数据。

### 后续

- `v0.4`：跨项目方法复用、能力证据和方向发现；
- `v0.5`：领域包、评测集和可安装技能；
- 多设备/协作/云端不预设版本，必须由真实需要触发。

## 8. 迁移决策

保留：

- 算法纯函数、执行轨迹和相关测试；
- SQLite 研究数据，作为迁移输入而非新 schema；
- Claude SDK 适配经验；
- Windows 打包经验。

归档或重写：

- 所有 PySide6 页面；
- 手工对象录入流程；
- 旧 tracker 和旧算法工作台；
- 当前 ResearchRepository schema；
- `v0.2.0-alpha` 的产品声明。

迁移必须是：备份 → dry-run 报告 → 用户确认 → 新库写入 → 数量/摘要校验 →
旧库只读保留。不得原地修改唯一副本。

## 9. 最大风险与控制

1. **范围爆炸**：每个版本只允许一个纵向用户旅程；横向平台能力随旅程出现。
2. **Tauri/Python 打包复杂**：先做 5–8 开发日技术切片，失败则比较本地 Web/PWA，
   不先写业务。
3. **Agent 误操作**：workspace 根限制、工具 schema、sandbox、预算、事件日志、
   diff/undo 和审批分级。
4. **伪科研**：Evidence locator、反例/基线、不可变 Run 和用户最终 Decision。
5. **解析器不可靠**：保留原始文件、解析版本、per-page failover 和可替换 adapter。
6. **用户被 UI 淹没**：驾驶舱低密度、Studio 高密度、上下文动作优于对象表单。
7. **只造平台不做研究**：每个 alpha 都必须使用一个真实问题完成并留下成果。

## 10. Codex 的强结论

- Nana 应以真实项目执行为主循环，个人成长为证据派生层；
- 当前 UI 和 ResearchRepository 都应重写，算法能力与数据只迁移、不继承界面；
- Tauri + React + Python sidecar 是首选，但必须先通过纵向技术切片；
- 高自治必须建立在本地优先、数据分级、sandbox、事件日志和可撤销写入之上；
- `v0.3.0` 应是重构线，不再把当前 `v0.2.0-alpha` 当成可继续扩展的产品骨架。

