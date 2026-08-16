# Nana 全面重构：共同证据包

> 截止日期：2026-07-29  
> 用途：Codex 与 Claude 必须先基于本文件独立提案，再交换提案和反驳。  
> 规则：事实、推论和建议必须分开；不得因另一方先发言而默认接受其结论。

## 1. 用户目标与已确认约束

用户希望 Nana 成为能够解放科研与工程生产力、同时使自己逐步成长为某一领域
算法工程师的长期个人项目。当前研究方向尚未确定，因此系统不能绑定单一领域。

已确认：

- 当前产品、功能、界面和技术实现都允许重构，没有既有对象或技术栈不可改变；
- 优先支持 Windows，未来投入周期较长，但没有固定每周工时；
- 界面采用“两层体验”：简洁的研究驾驶舱 + 项目内强大的科研 IDE；
- AI 目标为高自治：尽可能自主完成阅读、检索、编码、实验与整理，仅在高风险
  操作和最终成果处审批；
- 产品第一价值闭环不由用户预先指定，要求参考高质量项目及其版本演进后共同
  决策；
- `D:\Obsidian Vault\Nana_研究系统` 是废版。用户选择先备份，再以新的正式
  规划替换；
- 本对话只执行 Nana 全面重构研究、共同决策、Obsidian 落档及完整性/可行性/
  可执行性复核这一项总任务。

## 2. Nana 当前事实基线

### 2.1 版本历史

公开 Git 历史只有四次提交：

| 日期 | 版本/提交 | 变化 |
| --- | --- | --- |
| 2026-07-25 | 初始 AlgoMind | 约 770 行 |
| 2026-07-26 | `v0.1.0` | 滑动窗口学习工作区，新增约 927 行 |
| 2026-07-28 | 研究骨架 | 一次性新增约 6,947 行并删除约 506 行 |
| 2026-07-28 | `v0.2.0-alpha` | 主要修改版本文案 |

这意味着 Nana 尚未经历真实、连续的用户反馈迭代。`alpha` 标签不能被当作产品
闭环已经验证的证据。

### 2.2 当前实现

- Python 3.11、PySide6、Matplotlib、SQLite、PyInstaller；
- 研究对象：ResearchThread、Source、Claim、Evidence、Method、Experiment、
  Insight；
- 旧刷题数据库和算法演示代码仍在仓库，运行入口已部分退出；
- Claude 目前通过本地 Anthropic 兼容客户端和已配置的兼容中转站接入，只读讨论；
  Nana 不读取 `ANTHROPIC_API_KEY`，不直连官方 Anthropic，也不请求官方授权；
- 2026-07-29 全量测试 61 项通过；
- 尚无论文/PDF/仓库导入、证据定位、代码编辑器、终端、通用实验运行时、Agent
  行为日志、审批/撤销、跨项目复用或能力证据系统。

### 2.3 实机 UI 审查

当前窗口是固定侧栏 + 列表 + 详情卡：

- 侧栏只显示“研、迁、法、设”单字，识别成本高；
- Research Thread 详情依靠六个“+ 来源/+ 主张/+ 证据/+ 方法/+ 实验/+ 判断”
  按钮手工录入，用户需要理解数据库对象后才能工作；
- 资料阅读、代码、实验、AI 活动和最终产物没有连续工作空间；
- 方法实验室是预置算法表单，而非可运行任意代码、比较实验和保留产物的实验环境；
- 大量空白、长文本平铺和弱反馈使其既不像研究驾驶舱，也不像科研 IDE；
- 暖色主题不是主要问题；核心问题是信息架构仍围绕 CRUD，而非工作流。

## 3. 对标项目及版本演进事实

### 3.1 EAI

来源：

- <https://github.com/zGuanZhe/EAI>
- 仓库内 `docs/PRODUCT.md`、`ARCHITECTURE.md`、`DESIGN.md`、
  `VALIDATION.md`、`MIGRATION.md`

公开历史从 2026-07-17 的 0.4 工作区快照开始，2026-07-19 发布 1.0.0，
2026-07-20 发布 1.0.1。演进顺序大致为：

1. 建立桌面工作区；
2. 增加 schema 兼容桥；
3. 建立证据和 projection 基础；
4. 处理取消、SSE、未保存编辑和首次运行；
5. 重构 application service、workspace、router、Atlas 和 Agent 边界；
6. 统一 canonical writes；
7. 建立发布、迁移、只读降级、安装/卸载和真实数据不变性门槛。

值得吸收：

- ContextManifest、Evidence Guard、可打开定位与禁止伪造引用；
- canonical SQLite + 可重建 projection；
- 所有持久化操作采用 preview/confirm/receipt/undo；
- 能力注册表限制 Agent 权限；
- Docker 实验与宿主机隔离；
- React + Tauri + Python sidecar 适合富桌面科研工作区；
- 版本发布包含 schema ceiling、备份恢复、安装/卸载和真实用户数据不变性。

需要警惕：

- 公开历史是巨大已有代码快照后的短期集中发布，不能当作单人项目从零演进速度；
- 功能和对象很多，Nana 不应直接复制 Campaign/Atlas/Agent 的全部复杂度。

### 3.2 DeepTutor

来源：

- <https://github.com/HKUDS/DeepTutor>
- <https://github.com/HKUDS/DeepTutor/releases>

版本弧线：

- 2025-12-29 首次公开；
- 2026-04 的 1.0.0 进行 agent-native 架构重写；
- 1.2.x 继续补附件、知识库和使用可靠性；
- 1.3.x 大量版本处理模型路由、RAG、启动器、Book/Chat 连续性、多用户隔离和
  CORS；
- 1.4.0 将 Chat/Research/Solve/Question 统一到一个 Agent runtime，引入
  L1/L2/L3 Memory 和能力基础设施；1.4.1 立即修复 shell RCE、路径穿越、
  跨用户授权和聊天回归；
- 1.5.x 重点变为可恢复知识库、附件预算、原子写入、页面级引用、聊天流畅度、
  可追溯 RAG、Obsidian Vault 连接和多种本地编码 Agent。

值得吸收：

- 所有能力共用统一 Agent 运行时，不为每个页面复制一套流程；
- Session 累积来源、可检查 Memory、工具授权和 Activity 反馈；
- 失败文档可单独移除，长任务可恢复，写入原子化；
- UI 和后台配置使用同一事实来源；
- Obsidian 可以作为连接的知识来源，而不是重新发明用户的笔记库。

需要警惕：

- “功能很多”带来了安全补丁、跨模式不一致和持续 UI 回归；
- Nana 是单人研究工程系统，不应复制多用户、IM Partner、课程生成和 Book 等
  与主循环无关的产品面。

### 3.3 OpenScience

来源：

- <https://github.com/synthetic-sciences/openscience>
- <https://github.com/synthetic-sciences/openscience/blob/main/CHANGELOG.md>
- <https://github.com/synthetic-sciences/openscience/blob/main/ARCHITECTURE.md>

1.2.3–1.2.8 的连续版本并未主要堆科研技能，而是修复发布、首次运行、模型目录、
密钥/计费路由、网络超时、OAuth 恢复、技能打包和 UI 排版。当前采用本地服务、
浏览器工作区、HTTP+SSE、文件/终端/会话/科学视图和可选 blind reviewer。

值得吸收：

- “给目标 → 文献 → 假设 → 代码 → 实验 → 写作”的连续项目工作区；
- 文件树、编辑器、终端、会话和科学产物在同一个科研 IDE；
- 本地 server、localhost 限制、模型路由、技能和连接器可扩展；
- 先保证安装、首次运行、超时、凭据与 provider 可靠，再扩大技能目录。

需要警惕：

- 290+ skills 和众多科学连接器是长期生态结果，不是 Nana 首发范围；
- 全自动研究声称必须由可追踪实验和人工终审约束。

### 3.4 OpenMAIC

来源：

- <https://github.com/THU-MAIC/OpenMAIC>
- <https://github.com/THU-MAIC/OpenMAIC/releases>

版本弧线：

- 0.1.0 先建立沉浸课堂、语音、白板和快捷键；
- 0.1.1 补导入导出、语言、Provider、端到端 happy path 和安全；
- 0.2.0 扩展交互场景、在线编程并建立布局质量评测；
- 0.2.2 才增加生成前可编辑大纲、初版编辑器、undo/redo 与离线导出；
- 0.3.0 抽离 DSL/renderer SDK、PBL v2 和 AI 编辑；
- 0.3.1 进一步做直接操作编辑器、append-only runtime、outbox、server storage
  和视频导出。

值得吸收：

- 先让用户编辑生成计划，再支付完整生成成本；
- 交互产物使用稳定中间表示，渲染器与生成器解耦；
- AI 编辑采用 typed intent + validated patch，而不是任意改文件；
- 布局和生成质量需要 eval harness，不能只靠截图观感；
- undo/redo、离线导出和持久运行状态是核心能力。

### 3.5 STORM / Co-STORM

来源：

- <https://github.com/stanford-oval/storm>
- <https://github.com/stanford-oval/storm/releases>

1.0 对应论文与稳定知识策展流程；1.1 重点转向 LiteLLM 和检索器兼容。Co-STORM
引入多角色提问、动态知识图和人在回路协作。

值得吸收：

- 多视角提问先暴露知识缺口，再生成结构；
- 人可以在研究过程中插入方向，而不是只在末尾审核；
- Provider 与 Retriever 接口应可替换。

### 3.6 PaperQA2

来源：

- <https://github.com/Future-House/paper-qa>
- <https://github.com/Future-House/paper-qa/releases>

PaperQA2 从 5.x SemVer 转向 CalVer；2025-12 以后重点扩展表格、图片、非英文、
公式、Office、页码和多解析器。2026 年连续版本大量处理 parser failover、
非破坏重试、元数据匹配、JSON 兼容、内存和依赖可靠性。

值得吸收：

- 科研 RAG 的难点主要在解析、元数据、页码、上下文压缩、重排和失败恢复；
- Evidence 必须保存可回到原资料的位置；
- 新解析器应作为可替换适配器，并保留原始文件与解析版本。

### 3.7 MLflow、DVC、SwanLab

来源：

- <https://github.com/mlflow/mlflow>
- <https://github.com/iterative/dvc>
- <https://github.com/SwanHubX/SwanLab>

共同演进规律：

- 先用极低侵入 API 记录参数、指标、环境和产物；
- 再做比较、分组、筛选、baseline、复制、并行和恢复；
- 最后才扩展团队、注册表、部署、Agent trace 和评测。

值得吸收：

- 实验记录必须尽量自动采集，不能要求用户手工填完表单；
- Run 应不可变，比较和结论是派生视图；
- 环境、代码版本、输入、指标和 artifact 是最低复现单元；
- Nana 应对接现有 MLflow/DVC/SwanLab，而不是重写完整 MLOps 平台。

## 4. 从版本史得到的共同模式

1. **一个主循环先成立**：项目先靠单一主循环产生价值，随后才扩展模式。
2. **统一运行时优于页面堆叠**：Chat/Research/Solve 等最终都会被迫统一会话、
   工具、事件、记忆与权限。
3. **可编辑计划先于高成本执行**：预览、批准、运行、收据和撤销是高自治的基础。
4. **可靠性版本多于炫技版本**：首次运行、超时、断线、恢复、原子写入、迁移、
   凭据和安全会占据大量真实迭代。
5. **可追溯性不能后补**：来源 locator、代码版本、运行环境、Agent action 和
   用户终审必须进入第一版数据契约。
6. **高自治提高安全要求**：越自动，越需要 sandbox、最小权限、数据分级、运行
   预算、可中断性和审计日志。
7. **UI 应围绕连续任务而非数据库对象**：文件、阅读、代码、实验、AI 和成果
   要在同一项目上下文中切换。
8. **能力成长应由工作证据派生**：不能建设与真实项目分离的积分/等级系统。

## 5. 必须由共同提案回答的问题

1. Nana 的一句话产品定义和不可替代价值是什么？
2. 项目执行与个人能力成长是什么关系，谁是主循环？
3. 双层 UI 的信息架构、关键页面和默认工作流是什么？
4. 是否立即替换 PySide6；若替换，选择何种桌面/UI/后端组合？
5. 什么是最小但可扩展的领域模型、事件模型与 artifact 模型？
6. 高自治 Agent 可以默认做什么，哪些动作必须审批？
7. 公共论文、私人笔记、未公开代码和凭据如何分级与路由？
8. 版本如何从当前 `v0.2.0-alpha` 演进，首个可验证纵向切片是什么？
9. 如何迁移现有 SQLite、算法代码和 Obsidian 废版，哪些只归档不继承？
10. 用哪些验收场景、指标、测试和退出条件证明方案完整、可行、可执行？
