# Nana 最终对等会签包（脱敏）

> 日期：2026-07-29  
> 用途：Codex 与 Claude 在独立提案和交叉反驳之后，对最终方案逐项会签。  
> 隐私约束：仅包含获准的硬件型号与必要的软件版本；不包含设备序列号、授权信息、机主名、用户名、网络标识、密钥或含用户名的路径。

## 1. 协作方式与前两轮结论

Codex 与 Claude 是平等共同设计者。双方先读取同一证据包并独立提案，再互相读取完整提案、列出证据、风险、反驳与否决条件。共享的是可审查的显式论据，不声称展示任何模型的隐藏思维过程。

前两轮已经共同接受：

1. Nana 的唯一主循环应是 Project Execution，能力成长是派生视图；
2. 至少用 Algorithm Investigation、Paper/Repo Reproduction、Engineering Optimization 三种模板证明主循环不是空洞抽象；
3. 旧 PySide6 产品 UI 冻结，目标为 React/TypeScript + Python sidecar，先浏览器纵向切片再验证 Tauri 2；
4. 控制平面从首版包含 Project、Inquiry、Resource、Artifact、Plan、Run、Event、Approval/Receipt；
5. locator、不可变 Run、追加 Event、原子写和明确失败态进入首版契约；
6. 高自治采用策略预授权与预算内自动执行，而不是逐条确认或任意 shell；
7. 未知代码、环境改变、非公开数据外发、外部写入、删除和发布保留审批；
8. canonical SQLite / Artifact Store 是 Nana 的事实源，Markdown 知识库是连接与发布路径；
9. 可靠性、迁移、恢复、安全和 Windows 打包必须在 `v0.3.0` stable 前完成；
10. 旧算法演示和旧数据库只可作为示例 Artifact 或可选导入源，不应约束新 schema。

Claude 上轮留下三个否决项：

1. 机密任务缺少合格本地模型时必须有明确降级；
2. Windows 无强隔离后端时必须诚实限制未知代码自治；
3. 无固定工时时，每个 milestone 必须设 scope ceiling。

## 2. 允许披露的本机信息

- CPU 型号：Intel Core i9-14900HX；
- GPU 型号：NVIDIA GeForce RTX 5060 Laptop GPU；
- 当前审计运行时版本：Python 3.12.13；vNext sidecar 目标为 Python 3.12。

本机能力只能支持“本地模型按任务评测后进入有限白名单”的设计，不能据此承诺与前沿云模型等价。任何执行后端是否存在，都由 Nana 本地探测，不在本会签包披露。

## 3. 剩余否决项的候选处置

### 3.1 机密数据和模型降级

数据分级：`public / personal / confidential / secret`。

- Git、测试、静态分析、已注册转换器等确定性本地工具，按策略继续自动执行；
- Nana 提供本地模型适配器，可连接兼容服务；具体模型必须通过按任务类型划分的 EvalPack，才进入能力白名单；
- `confidential` 默认不向云端发送原文：
  - 有合格本地模型时，仅在已通过评测的能力范围自动运行；
  - 无合格本地模型时，AI 决策层明确降级，确定性工具仍可自动；
  - 用户可逐项目、逐 Provider 授权云端处理，或选择脱敏发送；
- `secret` 默认禁止发送到外部 Provider；密钥永不进入 Prompt、Artifact 或普通日志；
- 模型替换、能力降级和数据外发必须在 UI 与 Receipt 中可见。

### 3.2 Windows 执行边界

定义统一 `ExecutionBackend`：

- `builtin_local`：只运行 Nana 自带且版本锁定、参数 schema 固定的工具；
- `windows_sandbox`：可用时作为外部或不受信代码的 Windows 隔离后端；
- `docker`：可用时作为可复现隔离后端；
- 未来可增加远程隔离 Runner，但不进入 `v0.3.0`。

`builtin_local` 自动执行必须同时满足：

- 工作目录在项目 scratch/output；
- 路径解析后落在允许根目录；
- 命令、参数、网络、环境变量和副作用登记在 Capability Registry；
- 进程树、超时、CPU/内存和输出大小受限；
- 产生不可变 Run、追加 Event 和 Receipt；
- 禁止任意 shell 字符串拼接。

未知外部代码：

- 没有强隔离后端时，首次运行必须显式审批；
- 虚拟环境不是安全边界；
- 单次批准不自动变成永久信任；
- 产品不承诺无强隔离时对未知代码进行无审批高自治。

### 3.3 Milestone scope ceiling

不承诺日历日期。每个里程碑只能有一个端到端验收旅程，其余能力顺延。

| 里程碑 | 唯一验收旅程 | 必须完成 | 明确不做 |
|---|---|---|---|
| `v0.3.0-dev` | 真实算法 Inquiry 以最小 Resource/Locator、确定性测试形成 Finding draft，并审批导出无敏感测试报告 | Web + sidecar、Action/PolicyGrant/Event/Receipt、可恢复 Artifact commit、取消/失败态 | 完整检索、三实现、benchmark、Decision、PDF |
| `v0.3.0-alpha.1` | Algorithm Investigation | 公共来源、代码编辑、受控测试、反例、可追溯 Decision | PDF 解析、跨项目推荐 |
| `v0.3.0-alpha.2` | Paper/Repo Reproduction | PDF 页码 locator、repo commit/symbol、环境锁定、baseline 对比 | 全自动论文写作、多人协作 |
| `v0.3.0-beta` | Engineering Optimization | 基线、变更、实验矩阵、指标比较、回归门槛 | 领域 Agent 群、云同步 |
| `v0.3.0-rc` | 同一工作区备份、升级、崩溃恢复和审计 | schema ceiling、迁移 dry-run、恢复、安装/卸载、沙箱检查 | 新功能 |
| `v0.3.0` | 三模板共同通过发布门槛 | 零伪造引用、零越权执行、数据不变性、Windows 打包 | 未通过门槛的扩展 |
| `v0.4.x` | 跨项目复用一个已验证 Artifact/Method | 检索、复用来源、CapabilityEvidence 派生视图 | 社交、排名、泛课程系统 |
| `v0.5.x` | 一个用户确认的领域包 | 领域 ontology/eval/template 插件化 | 预先押注具体科研领域 |

## 4. D1–D10 最终候选决策

请逐项给出 `ACCEPT` 或 `VETO`。`VETO` 必须给出可检验的解除条件；`ACCEPT` 可附最多一句边界。

### D1 产品宪章

Nana 是 local-first、可追溯、高自治的个人 Research & Engineering OS：把真实科研或工程问题推进为可验证结论、可复现实验、可复用工件和可证明能力。它不是文献聊天器、课程播放器、算法刷题站，也不是自动发论文机器。

### D2 唯一主循环

`目标/问题 → 研究与证据 → 假设与计划 → 实现与实验 → 比较与反证 → 决策与交付 → 跨项目复用`。

三种 Plan Template 共享同一控制平面；能力成长是工作证据的派生视图，不是独立游戏化主循环。

### D3 首批垂直切片

技术切片 → 算法调查 → 论文/仓库复现 → 工程优化。技术切片和算法调查使用真实问题；首个算法问题在实施前由用户确认。

### D4 界面

- Research Cockpit：目标、项目、待审批、运行中/失败 Run、关键发现、预算和入口；
- Research Studio：左侧项目/资源/产物树，中间 PDF/Markdown/代码/图表编辑区，右侧 AI 计划/证据/动作/成本/暂停/撤销，底部终端/运行日志/测试/指标。

界面围绕连续任务而非数据库实体 CRUD 设计。

### D5 技术栈与迁移

- React + TypeScript 前端；
- Python 3.12 FastAPI sidecar；
- 先浏览器切片，再用 Tauri 2 / Rust 包装并验证 Windows 生命周期、崩溃与打包；
- 唯一 Plan B 是本地 Web 工作区，不维护新 Qt 双栈；
- SQLite WAL + 内容寻址 Artifact Store；
- DuckDB/Parquet 按实验规模引入；
- Git、DVC、MLflow/SwanLab、Jupyter 使用适配器，不重新实现。

### D6 数据契约

稳定控制平面：Project、Inquiry、Resource、Artifact、Plan、Run、Action、
PolicyGrant、Event、Approval/ActionReceipt。

研究语义：Claim、Evidence、Hypothesis、Method、Finding、Decision。

所有引用带 locator；Run 的 identity/冻结快照/终态结果不可覆盖，生命周期由 Event
派生；Event 支持 aggregate/actor，关系类型注册并校验。知识库是发布路径，不是
事务数据库。

首批每一种 Relation 均固定 source/target、outgoing/incoming cardinality、删除
行为、跨项目规则与结构化错误；领域对象、Run 与 Action 均有服务端状态迁移表，
非法边统一拒绝。最终 Decision 是内置 T4 `decision.confirm` Action；action hash
覆盖 Decision revision、Evidence/Finding manifest、备选、限制和重评条件，只能
由绑定该 hash 的一次性 Approval 授权，PolicyGrant 不得代批。

### D7 高自治

策略预授权 + 预算内自动执行：

- 公开网络读取、注册的只读/分析工具可自动；
- scratch 内可逆写、注册测试/构建可自动并出具 Receipt；
- 未知代码、环境改变、工作区外访问、非公开数据外传、外部写入需审批；
- 删除、发布、最终 Decision 需审批；
- token、调用次数、墙钟时间、网络、CPU/内存和工作区范围进入 Run Budget。

### D8 隐私与执行

采用第 3.1 和 3.2 节的能力评测、诚实降级和 `ExecutionBackend` 边界。没有隔离后端时不承诺未知代码无审批自治；没有合格本地模型时不承诺机密 AI 决策层保持同等能力。

### D9 版本治理

采用第 3.3 节的单旅程 scope ceiling。统一 Runtime 和可靠性从 `v0.3.0-dev` 开始，迁移、恢复和审计在 stable 前完成。

### D10 发布门槛

稳定版至少通过：

- 三种 Plan Template 的端到端验收；
- 引用 locator 完整且零伪造；
- 工具调用零越权，审批不可绕过；
- 崩溃/取消后状态明确，原子写不破坏数据；
- 备份、迁移 dry-run、恢复演练和 schema ceiling；
- Windows 安装、升级、卸载与数据目录不变性；
- 预算生效，Run 可回放到行动、证据、代码、环境和结果；
- 知识库发布需要 Approval/Receipt，且不与 canonical 数据冲突。

alpha.1 的主观门槛已转为可判定协议：反例搜索先冻结输入域、生成器、随机种子和
case/time budget；未找到只形成有范围的 Finding。最终报告的每一条外部事实必须
关联可重开的 typed Evidence/Run，或显式标为 Hypothesis/Opinion/Unverified。
30 分钟观察测试要求完成 create→plan→run→approve→artifact，最多两次澄清、
10 个状态问题至少答对 8 个，且无成败/审批/已提交数据的关键误解。

## 5. 要求的最终输出

1. D1–D10 逐项 `ACCEPT` 或 `VETO`；
2. 是否存在阻塞正式规划落盘的剩余分歧；
3. 对完整性、技术可行性、单人长期可执行性的结论；
4. 最多五个实施期硬门槛；
5. 明确区分事实、推断和未验证假设。
