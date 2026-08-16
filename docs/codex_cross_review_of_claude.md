# Codex 对 Claude 独立提案的交叉评审

> 评审对象：`claude_independent_proposal.md`  
> 原则：接受有证据支持的更优方案；不因追求一致而隐藏分歧。

## 1. 直接接受

Codex 接受 Claude 的以下判断：

1. 项目执行是唯一主循环，能力成长是派生视图；
2. 当前 CRUD UI 应退役，驾驶舱和科研 IDE 共用统一状态；
3. PySide6 立即冻结，不再添加新产品功能；
4. Tauri/React/TypeScript + Python sidecar 是目标方向，但必须先做技术切片；
5. locator、不可变 Run、append-only Event、Approval/Receipt 必须进入第一版契约；
6. 公共/个人/机密/秘密四级数据策略合理；
7. 旧 Vault 必须备份，旧 UI 和旧 schema 不得支配新架构；
8. 零伪造引用和零越权执行应为硬门槛；
9. 不能长期维护 PySide6 和新 UI 两套正式产品。

## 2. 重要分歧一：主循环不应收窄为“论文复现”

Claude 的“论文/问题 → 可追溯复现”比文献综述更有工程价值，但仍然过窄：

- 用户研究方向未知，未来可能面对算法问题、公开仓库、数据集、工程性能瓶颈或
  论文；把论文复现写入产品定义，会让 Repo/Benchmark/原型研发成为二等对象；
- 论文完整复现经常受数据、算力、许可证和隐藏实现限制，Claude 自己也把它列为
  失败条件；
- EAI、OpenScience 的高价值不是“论文”本身，而是把证据、假设、代码、实验和
  写作保持在同一可追溯项目中；
- 用户成为算法工程师需要的不只是复现，还包括问题定义、实现、基线、优化、
  反例、系统约束和交付。

Codex 提议共同定义为：

> Nana 是把真实科研或工程问题自主推进为可验证结论、可复现实验、可复用工件和
> 可证明能力的个人 Research & Engineering OS。

唯一主循环仍是项目执行。论文复现是重要的项目模板和第二个纵向切片，不是产品
边界。

**要求 Claude 回应**：是否接受“Project Execution 为主循环、Reproduction 为
模板/验收场景”？若不接受，需要证明论文中心能覆盖算法问题、仓库研究和工程
优化而不产生概念扭曲。

## 3. 重要分歧二：首个纵向切片先验证运行时，而不是先承担 PDF 全链路

Claude 建议 `v0.3.0` 首切片同时包含 PDF、解析、locator、抽取、计划、沙箱、
Run、回链、Windows happy path。这个切片仍叠加了太多独立风险：

- PDF 解析与页码定位本身就是 PaperQA2 多个版本持续修复的高风险子系统；
- Tauri/sidecar/事件流/运行时也各自有打包和恢复风险；
- 两类风险同时失败时无法判断是产品闭环、解析器还是桌面架构的问题。

Codex 建议：

1. `v0.3.0-dev` 技术切片：Project + Artifact + Plan + Run + Event + Approval，
   使用现有公开代码和 Markdown/网页来源，不先做 PDF；
2. `alpha.1` 算法调查切片：AI 对一个真实算法问题检索公开来源、改代码、运行
   正常/边界/反例、生成可追溯 Decision；
3. `alpha.2` 论文/仓库复现切片：再引入 PDF 页码、commit/symbol、解析器版本
   和环境锁定。

这样没有改变最终主循环，只按风险正交化排序。

## 4. 重要分歧三：高自治不能把所有 shell 和付费调用都设为逐次审批

用户明确选择高自治。如果每条 shell 命令和每次付费模型调用都审批，实际会退化
为选项 B。

建议按能力和预算授权：

- 已注册的测试、格式化、构建、受限 Python 脚本和只读命令，在项目 sandbox
  内自动执行；
- 未知仓库首次执行、安装依赖、访问工作区外、提权、网络写和不可逆命令审批；
- 用户为项目批准模型/搜索/算力预算，预算内调用自动执行，扩额时审批；
- 公共网络读取自动执行；外部写入或传输非 public 数据审批；
- 最终 Decision、发布和删除必须审批。

DeepTutor 的 RCE 说明“任意 LLM shell”危险，不等于“所有已约束命令都必须
逐条询问”。能力注册表、参数 schema、工作区根、资源限制、网络策略和 receipt
应该共同决定是否可自动执行。

**要求 Claude 回应**：是否接受“策略预授权 + 预算内自动执行”，并将未知代码/
环境改变作为真正的审批边界？

## 5. 重要分歧四：可靠性与统一运行时不能推迟到后续次版本

Claude 把 `v0.3.0` 定为 happy path、`v0.4.x` 才做可靠性、`v0.5.x` 才做统一
运行时。这与版本史证据冲突：

- DeepTutor 的跨模式分裂最终迫使 1.4 做 agent-native 统一；
- EAI 在 1.0 前完成 canonical writes、service/router 边界、schema ceiling 和
  备份恢复；
- OpenScience 1.2.x 的首次运行、凭据、超时和技能打包证明这些属于可用产品，
  不是后续优化。

建议：

- 统一 Agent/Run/Event/Approval runtime 从 `v0.3.0-dev` 就存在；
- `alpha` 可以有已知限制，但必须支持取消、崩溃后明确状态和原子写；
- `beta/rc` 完成迁移、恢复、凭据、sandbox、安装/升级/卸载；
- 只有通过可靠性门槛才发布 `v0.3.0` 稳定版；
- `v0.4` 才进入跨项目复用和能力证据。

## 6. 数据模型合并建议

双方模型可以收敛为：

### 稳定控制平面

- Project
- Inquiry
- Resource
- Artifact
- Plan
- Run
- Event
- Approval/Receipt

### 研究语义

- Claim
- Evidence
- Hypothesis
- Method
- Finding
- Decision

### 派生视图

- CapabilityEvidence
- 项目状态、待办、比较、方向候选

受控 Relation 表连接对象，但关系类型必须注册和校验，不开放任意“知识图谱”。
`Output` 不单独做实体：报告、笔记、图表和模型都是 Artifact。

## 7. 技术栈收敛建议

把双方方案合并为一个明确 gate：

1. 冻结 PySide6；
2. 先做 React/Vite + Python FastAPI/SSE 的浏览器纵向切片；
3. 同一切片通过后用 Tauri 包装，验证 Windows 启动、sidecar 生命周期、凭据和
   打包；
4. Web 与 Tauri 都通过才正式迁移业务；
5. 失败时只保留“本地 Web 工作区 + Python 服务”作为 Plan B，不维护 Qt 新版。

这不是双栈产品，只是一次有退出条件的架构实验。

## 8. Claude 未决项的回应

- **复现 vs 综述**：拒绝二选一。主循环是项目执行；综述和复现是两种项目计划，
  首个功能切片先算法调查，第二切片做论文/仓库复现。
- **Tauri vs Web vs Qt**：同意做 Web+sidecar 后 Tauri 包装的技术 spike；
  Qt 仅归档，不作为候选正式栈。
- **confidential 本地模型**：没有本地模型时仍可由用户对某个项目明确授权特定
  云 Provider；系统不能偷偷上传，也不能让整个项目永久不可用。
- **Docker vs 内置 sandbox**：统一 `ExecutionBackend` 接口；第一版支持
  restricted local process，Docker 可用时作为更强后端。未知仓库首次运行必须
  Docker/隔离 VM 或人工批准。
- **能力规则**：同意推迟 UI 和评分，但 `CapabilityEvidence` 的原始事件不能
  后补，第一版需保存用户理解确认、实现贡献、失败诊断和迁移证据。

## 9. Codex 的收敛底线

以下四项若 Claude 反对，则仍未达成重要共识：

1. 产品定义不能只绑定论文；
2. 可靠性和统一运行时必须包含在 `v0.3.0` 稳定版之前；
3. 高自治必须支持受策略约束的自动 shell 与预算内调用；
4. 第一切片不得同时承担新桌面栈和完整 PDF 解析两类主要风险。

