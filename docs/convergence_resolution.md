# Nana 重构：最终收敛候选与剩余否决项处置

> 日期：2026-07-29  
> 角色：Codex 与 Claude 为平等的产品、研究与工程共同设计者  
> 阶段：本地收敛草案；未作为最终会签包发送  
> 可见性原则：共享结论、证据、假设、风险、反驳与否决条件；不声称暴露任何模型的隐藏思维过程。

> [!warning]
> 本文包含比用户后续允许范围更详细的本机资源摘要。首次发送尝试被安全审查拦截，
> 未向中转站发送；此后只使用
> `docs/claude_final_review_packet_sanitized.md`。脱敏包不含序列号、授权信息、
> 机主名、用户名、网络标识、密钥、含用户名路径、内存或显存容量。

## 1. 新增事实

### 1.1 当前 Windows 设备

- CPU：Intel Core i9-14900HX，24 核 / 32 线程；
- 内存：15.7 GiB；
- GPU：NVIDIA RTX 5060 Laptop，8151 MiB 显存；
- 当前没有 Docker、Podman、Ollama；
- `wsl.exe` 存在，但 WSL 尚未安装。

### 1.2 可用执行与本地模型路径

- Windows Sandbox 支持关闭网络、只读映射宿主目录、限制内存；可把源目录只读映射，把输出写入单独目录。
  官方资料：
  - https://learn.microsoft.com/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file
  - https://learn.microsoft.com/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-sample-configuration
- Docker Desktop 可以作为后续更强的隔离后端，但当前设备没有安装，不能把它当作首版前提：
  - https://docs.docker.com/desktop/setup/install/windows-install/
- Ollama 和 LM Studio 均支持 Windows 本地模型；LM Studio 提供 OpenAI / Anthropic 兼容本地 API。
  - https://docs.ollama.com/windows
  - https://lmstudio.ai/docs/app/system-requirements
  - https://lmstudio.ai/docs/developer/rest

### 1.3 从硬件事实得出的边界

- 16 GiB 内存和 8 GiB 显存足以运行部分小型或中型量化模型，用于抽取、分类、简单改写、有限代码辅助和低风险规划；
- 不能据此承诺本地模型具有前沿云模型相同的复杂科研推理质量；
- 所以“机密项目一律由强本地模型高自治完成”不可作为产品承诺；
- 正确做法是能力评测、明确降级和逐项目授权，而不是假装能力等价。

## 2. 三个剩余否决项的候选处置

### 2.1 机密数据与本地模型

采用四级数据分类：`public / personal / confidential / secret`。

1. 确定性本地工具（Git、测试、静态分析、已注册转换器）可按策略继续自动执行；
2. Nana 提供模型适配器接口，首选可接 LM Studio 或 Ollama，但具体模型只有通过 Nana EvalPack 后才进入对应能力白名单；
3. 本地模型评测结果必须按任务类型登记，不能用一个总分宣称“可用于科研”；
4. `confidential` 项目默认不向云端发送原文：
   - 有合格本地模型：仅在通过评测的能力范围内自动执行；
   - 无合格本地模型：AI 决策层明确降级，保留确定性工具自动化；
   - 用户可逐项目、逐 Provider 明确授权云端处理，或选择脱敏后发送；
5. `secret` 数据默认禁止发送到任何外部 Provider；密钥本身永不进入 Prompt、日志或 Artifact；
6. 降级必须在 UI 中可见，不得静默换模型或上传数据。

这不是“本地能力与云端能力等价”的承诺，而是诚实的能力边界。

### 2.2 Windows 无 Docker 时的执行边界

统一 `ExecutionBackend`：

- `builtin_local`：仅运行 Nana 自带、签名/版本锁定、参数 schema 固定的工具；
- `windows_sandbox`：运行外部或不受信代码的首选 Windows 强隔离后端；
- `docker`：用户未来安装后可启用的可复现强隔离后端；
- 未来可以增加远程隔离 Runner，但不进入 `v0.3.0`。

`builtin_local` 的自动执行要求：

- 工作目录限定在项目 scratch/output；
- 路径参数解析后必须落在允许根目录；
- 命令、参数、网络、环境变量和副作用在 Capability Registry 中登记；
- 进程树、超时、CPU/内存、输出大小受限；
- 每次执行产生不可变 Run、追加 Event 和 Receipt；
- 不允许任意 shell 字符串拼接。

外部未知代码：

- 没有 Windows Sandbox 或 Docker 时，首次运行必须显式审批；
- `venv` 不是安全边界；
- 不承诺无隔离后端时对未知外部代码进行无审批高自治；
- 用户批准本次运行也不能自动扩展为永久信任。

### 2.3 无固定工时时的范围上限

不承诺日历日期；用“每个里程碑恰好一个端到端验收旅程 + 明确不做项”控制范围。

| 里程碑 | 唯一验收旅程 | 必须完成 | 明确不做 |
|---|---|---|---|
| `v0.3.0-dev` | 一个真实算法问题可从目标进入计划、运行、事件、审批和产物 | Web + sidecar 技术切片，统一 Runtime，取消/失败态/原子写 | PDF 全链路、插件市场、能力评分 |
| `v0.3.0-alpha.1` | Algorithm Investigation | 公共来源、代码编辑、受控测试、反例、可追溯 Decision | 论文 PDF 解析、跨项目推荐 |
| `v0.3.0-alpha.2` | Paper/Repo Reproduction | PDF 页码 locator、repo commit/symbol、环境锁定、baseline 对比 | 全自动论文写作、多人协作 |
| `v0.3.0-beta` | Engineering Optimization | 基线、变更、实验矩阵、指标比较、回归门槛 | 领域专用智能体群、云同步 |
| `v0.3.0-rc` | 同一工作区备份、升级、崩溃恢复和审计 | schema ceiling、迁移 dry-run、恢复、安装/卸载、权限与沙箱检查 | 新功能 |
| `v0.3.0` | 三模板共同通过发布门槛 | 零伪造引用、零越权执行、数据不变性、Windows 打包 | 任何未通过门槛的扩展 |
| `v0.4.x` | 跨项目复用一个已验证 Artifact/Method | 检索、复用来源、CapabilityEvidence 派生视图 | 社交、排名、泛化课程系统 |
| `v0.5.x` | 一个用户确认的领域包 | 领域 ontology/eval/template 的插件化 | 预先押注具体科研领域 |

若某里程碑的唯一旅程未通过，不得以“已完成若干页面/接口”宣告完成。

## 3. 最终候选决策

请对每项分别给出 `ACCEPT` 或 `VETO`；`VETO` 必须包含可检验的解除条件。

### D1 产品宪章

Nana 是 local-first、可追溯、高自治的个人 Research & Engineering OS：把真实科研或工程问题推进为可验证结论、可复现实验、可复用工件和可证明能力。它不是文献聊天器、课程播放器、算法刷题站，也不是自动发论文机器。

### D2 唯一主循环

`目标/问题 → 研究与证据 → 假设与计划 → 实现与实验 → 比较与反证 → 决策与交付 → 跨项目复用`。

Algorithm Investigation、Paper/Repo Reproduction、Engineering Optimization 是三个 Plan Template，共享同一控制平面；能力成长是工作证据的派生视图，不是独立游戏化主循环。

### D3 首批垂直切片顺序

技术切片 → 算法调查 → 论文/仓库复现 → 工程优化。技术切片和算法调查必须使用真实问题；首个算法问题须在实施前由用户确认。

### D4 界面

采用双层界面：

- Research Cockpit：目标、项目、待审批、运行中/失败 Run、关键发现、预算和入口；
- Research Studio：左侧项目/资源/产物树，中间 PDF/Markdown/代码/图表编辑区，右侧 AI 计划/证据/动作/成本/暂停/撤销，底部终端/运行日志/测试/指标。

围绕连续任务设计，不围绕数据库实体 CRUD 设计。旧 PySide6 UI 冻结归档。

### D5 技术栈与迁移

- React + TypeScript 前端；
- Python 3.11 FastAPI sidecar；
- 先做浏览器纵向切片，再用 Tauri 2 / Rust 包装并验证 Windows 生命周期、崩溃和打包；
- 失败时唯一 Plan B 是本地 Web 工作区，不维护新的 Qt 双栈；
- SQLite WAL 为 canonical 元数据与事件事实源；
- 内容寻址 Artifact Store；
- DuckDB/Parquet 仅在实验数据规模需要时引入；
- Git、DVC、MLflow/SwanLab、Jupyter 通过适配器复用，不重新实现。

### D6 数据契约

稳定控制平面：Project、Inquiry、Resource、Artifact、Plan、Run、Event、Approval/Receipt。

研究语义：Claim、Evidence、Hypothesis、Method、Finding、Decision。

所有引用必须带 locator；Run 不可变，Event 追加写，关系类型注册并校验。Obsidian 是连接/发布路径，不是 Nana 的事务数据库。

### D7 高自治

采用“策略预授权 + 预算内自动执行”：

- 公开网络读取、注册的只读/分析工具可自动；
- scratch 内可逆写、注册测试/构建可自动并出具 Receipt；
- 未知代码、环境改变、工作区外访问、非公开数据外传、外部写入需审批；
- 删除、发布、最终 Decision 需审批；
- token、调用次数、墙钟时间、网络、CPU/内存和工作区范围均进入 Run Budget。

### D8 隐私与执行

采用第 2.1 与 2.2 节的诚实降级、能力评测和 `ExecutionBackend` 边界。没有隔离后端时不承诺未知代码无审批自治；没有合格本地模型时不承诺机密 AI 决策层保持同等能力。

### D9 版本治理

采用第 2.3 节的单旅程 scope ceiling。统一 Runtime 和可靠性从 `v0.3.0-dev` 开始，迁移/恢复/审计在 stable 前完成，不能推迟为“以后再补”。

### D10 发布门槛

稳定版至少通过：

- 三种 Plan Template 的端到端验收；
- 引用 locator 完整且零伪造；
- 工具调用零越权，审批不可绕过；
- 崩溃/取消后状态明确，原子写不破坏数据；
- 备份、迁移 dry-run、恢复演练和 schema ceiling；
- Windows 安装、升级、卸载与数据目录不变性；
- 预算生效，Run 可回放到行动、证据、代码、环境和结果；
- Obsidian 发布需要 Approval/Receipt，且不与 canonical 数据冲突。

## 4. 当前风险与未来实施门

以下不是本次规划的阻塞项，但必须成为实施门：

1. 用户确认首个真实算法调查问题；
2. 技术切片通过后才正式迁移业务；
3. Windows Sandbox 可用性探测失败时，未知代码保持审批模式；
4. 本地模型必须先通过 EvalPack，不能仅按模型名称授权；
5. 任一里程碑超出单旅程范围时，推迟功能而非扩张范围；
6. 任何对外发布或不可逆操作均保留最终用户审批。
