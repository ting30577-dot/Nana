# Claude 对 Codex 提案与反驳的交叉评审

> 形成时间：2026-07-29  
> 输入：共同证据包、双方独立提案、Codex 对 Claude 的完整反驳。  
> 状态：第二轮交叉评审，不代表最终共同结论。

## 总体结论

Claude 判断 Codex 提案整体质量高。对四项核心分歧的表态：

- 主循环：**条件接受**；
- 首个切片风险拆解：**接受，认为优于 Claude 原方案**；
- 高自治审批粒度：**条件接受**；
- 可靠性进入 `v0.3.0`：**接受，承认原路线推迟过晚**。

## 决策依据摘要

### 事实

- Nana 只有四次提交，从未经历真实迭代；当前是 CRUD，无 PDF/通用实验/Agent
  日志；
- 对标项目版本史表明可靠性、统一运行时和可追溯性是结构性成本；
- EAI 在 1.0 前完成 canonical writes、schema ceiling、备份恢复和数据不变性；
- DeepTutor 1.4 才统一运行时，1.4.1 随即修复 RCE 和越权；
- 用户研究方向未定，也没有固定工时。

### 推论

- “论文复现”进入产品定义会让算法问题和仓库研究成为概念弯路；
- PDF 解析和新桌面架构同时进入首切片，失败时无法归因；
- 逐条 shell 审批会抵消高自治价值。

### 未验证假设

- 有满足 confidential 任务的本地或私有模型；
- Windows 可以使用 Docker 或等效沙箱；
- 用户未来项目中有足量结构化算法调查问题。

## 对四项分歧的逐项回应

### 1. 主循环

**条件接受 Project Execution。**

Claude 要求显式列举并验证至少三种项目计划模板：

1. Algorithm Investigation；
2. Paper/Repo Reproduction；
3. Engineering Optimization。

统一主循环必须证明能表达三者而不产生概念扭曲，否则“Project Execution”只是
过度抽象的空词。

### 2. 首个切片

**接受技术切片 → 算法调查 → 论文/仓库复现的风险拆解。**

补充条件：

- `v0.3.0-dev` 必须使用真实用户问题，不能是 Hello World；
- 算法调查的问题应由用户在切片开始前确认，不能由 AI 自主替用户选择。

### 3. 高自治

**条件接受“策略预授权 + 预算内自动执行”。**

条件：

1. 每个工具具有显式参数 schema 和允许的 side effects；
2. Agent 只能调用注册工具，schema 外调用必须拦截；
3. 未知仓库首次执行必须 Docker/隔离环境或显式审批；
4. token、调用次数和运行时间预算进入第一版 Run 模型。

### 4. 可靠性时序

**接受。**

- `v0.3.0-dev` 建立统一 Run/Event/Approval runtime，支持取消、原子写和崩溃
  后明确状态；
- alpha 可以有已知限制，但不得损坏数据；
- beta/rc 完成迁移、恢复、凭据、sandbox、安装/升级/卸载；
- 稳定版 `v0.3.0` 通过全部可靠性门槛。

## Claude 指出的 Codex 缺口

### 1. confidential 数据通道

如果没有可用本地/私有模型，最重要的未公开代码与实验数据无法兑现高自治。
不能只说“让用户批准云 Provider”，需要：

- 至少一种经过评测的本地或私有模型路径；或
- 明确降级：confidential 项目中的 Git/DVC/测试等确定性工具继续自动执行，
  AI 决策层降级为本地弱模型、脱敏云请求或人工操作。

### 2. Windows restricted process 未定义

Windows 缺少 Linux `seccomp` 的直接等价物。venv 不能阻止网络和越权，
Job Object/AppContainer 又有工程成本。因此技术切片必须明确首版安全边界。

可接受的诚实结论是：

- Nana 自带的签名/注册脚本可以在受限工作区自动运行；
- 外部未知代码首次运行必须使用 Docker/隔离 VM 或得到用户审批；
- 没有 Docker 时，不承诺未知外部代码的无审批自治。

### 3. Obsidian 时序

必须从 `v0.3.0-dev` 明确：

- Nana canonical SQLite/Artifact Store 是一级事实来源；
- Obsidian 是连接与发布路径，不是事务数据库；
- dev/alpha 产物先保存在 Nana，再按 Approval/Receipt 写出 Obsidian。

### 4. 无固定工时

路线图不能以功能清单无限增长。每个 milestone 只允许一个端到端验收场景；其余
能力顺延。版本使用 scope ceiling，而不是承诺日历日期。

## 候选共同决策

### 已共识

1. 项目执行是唯一主循环，能力成长为派生视图；
2. PySide6 立即冻结；
3. 目标栈为 Tauri/React/TS + Python sidecar，先做技术切片；
4. 技术顺序是浏览器工作区 → Tauri 包装 → 正式迁移；Plan B 为本地 Web；
5. locator、不可变 Run、append-only Event、Approval/Receipt 进入第一版契约；
6. public/personal/confidential/secret 四级数据；
7. 零伪造引用、零越权执行为 CI 硬门槛；
8. 废版 Vault 先备份再替换；旧 UI/schema 归档而非继承；
9. 数据模型分稳定控制平面、研究语义、派生视图；Output 归入 Artifact；
10. 统一运行时从 `v0.3.0-dev` 开始，可靠性必须在 `v0.3.0` 稳定版前完成；
11. 旧刷题 DB 与算法演示只作为示例 Artifact，不迁移 schema；
12. Git、DVC、MLflow、Jupyter 采用适配层，不重新实现。

### 附条件共识

1. Project Execution 为主循环：三种模板都必须被统一表达；
2. 策略预授权：工具注册表、资源/网络/工作区策略必须形式化；
3. 首切片先算法调查：必须是真实用户问题；
4. CapabilityEvidence：第一版保存原始信号，但不做评分 UI；
5. canonical SQLite 为事实来源：Obsidian 只作为连接/发布路径。

### 第二轮仍有否决

1. confidential 任务的本地/私有模型或明确降级策略；
2. Windows 无 Docker 时的执行边界；
3. 每个 milestone 的 scope 上界必须明确。

