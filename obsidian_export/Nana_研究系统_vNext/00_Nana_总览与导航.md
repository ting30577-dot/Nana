---
title: Nana 研究系统总览与导航
aliases:
  - Nana vNext
  - Nana Research & Engineering OS
status: confirmed
date: 2026-07-29
owners:
  - user
  - Codex
  - Claude
tags:
  - nana
  - product
  - index
---

# Nana 研究系统总览与导航

> [!abstract] 一句话
> Nana 是 **local-first、证据可追溯、高自治的个人 Research & Engineering OS**：把真实科研或工程问题推进为可验证结论、可复现实验、可复用工件和可证明能力。

## 1. 这次重构改变了什么

当前 `v0.2.0-alpha` 是可运行的研究骨架，不是已经验证的产品。2026-07-29 使用
项目 `.venv`（Python 3.12.13）执行 `python -m unittest discover -s tests -v`，
61/61 通过；这只证明
遗留回归基线。当前还有 SQLite 数据和一套 PySide6 界面，但核心交互仍是手工维护
Source / Claim / Evidence / Method / Experiment / Insight，缺少连续阅读、代码、
实验、Agent 活动、审批、撤销和复现工作流。

新版不修补旧页面，而是重新定义：

- **产品主循环**：项目执行，而不是资料管理或独立能力打分；
- **默认体验**：Research Cockpit + Research Studio；
- **高自治方式**：策略预授权、能力注册、运行预算、隔离执行、全程 Receipt；
- **事实来源**：Nana 的 SQLite / Artifact Store；Obsidian 是规划、连接和发布路径；
- **技术边界**：React/TypeScript + Python sidecar，验证后用 Tauri 2 包装；
- **发布标准**：三种项目模板和可靠性门槛共同通过，才可称为 `v0.3.0`。

## 2. 已确认的用户决策

| 事项 | 决策 |
|---|---|
| 长期目标 | 解放科研/工程生产力，并使用户成长为某领域算法工程师 |
| 当前研究方向 | 尚未固定，因此产品不能绑定单一领域 |
| 第一价值闭环 | 由对标项目证据与 Codex/Claude 对等评审决定 |
| UI | 双层“研究驾驶舱 + 强研究 IDE” |
| AI 自治 | 高自治，仅高风险动作与最终成果保留审批 |
| 平台优先级 | Windows first |
| 开发节奏 | 长期维护、无固定周工时；用范围门槛而非日历承诺 |
| 旧 Vault | 备份后以本规格替换 |
| 既有约束 | 没有什么不能改；只保留被证据证明值得保留的部分 |

## 3. 唯一主循环

```mermaid
flowchart LR
    A["目标 / 真实问题"] --> B["研究与证据"]
    B --> C["假设与可编辑计划"]
    C --> D["实现与实验"]
    D --> E["比较、反例与反证"]
    E --> F["Decision 与交付"]
    F --> G["跨项目复用"]
    E --> C
    G --> A
```

首批三个 Plan Template：

1. **Algorithm Investigation**：理解算法边界、构造反例、实现并验证；
2. **Paper/Repo Reproduction**：把论文主张落到可定位证据、代码、环境和 baseline；
3. **Engineering Optimization**：定义基线、修改实现、运行实验矩阵并验证回归。

三者共享 Project / Plan / Run / Event / Artifact / Approval 等控制平面，不建设三套
互不兼容的产品。

## 4. 阅读顺序

1. [[01_联合产品宪章]]：Nana 是什么、服务谁、什么不做；
2. [[02_对标平台与版本演进]]：决策证据和迭代规律；
3. [[03_用户旅程与功能系统]]：三个端到端旅程和完整功能地图；
4. [[04_界面重构与交互规范]]：驾驶舱、Studio 和交互契约；
5. [[05_技术架构与数据契约]]：语言、进程、数据、事件、适配器；
6. [[06_AI自治_安全与隐私]]：审批、数据分级、模型路由和执行边界；
7. [[07_版本路线图与验收门槛]]：每个版本唯一旅程、范围上限和退出条件；
8. [[08_迁移_备份_发布与恢复]]：旧系统归档、数据迁移、回滚；
9. [[09_Codex_Claude对等决策记录]]：双方独立提案、反驳和条件共识；
10. [[10_完整性_可行性_可执行性终审]]：最终审计与风险结论；
11. [[11_首个纵向切片执行清单]]：下一步可以直接执行的工程任务；
12. [[12_验证记录与证据索引]]：测试 manifest、冻结版本证据与部署审计。

## 5. 状态词

| 状态 | 含义 |
|---|---|
| `confirmed` | 已由用户选择或双方证据收敛，可作为架构约束 |
| `implementation-gate` | 实施前必须用代码、测试或用户确认解除 |
| `deferred` | 有价值但不进入当前版本 |
| `rejected` | 有明确证据不应采用 |
| `unverified` | 当前只有合理推断，不得写成已完成事实 |

## 5.1 规范性用语与术语

为避免 `confirmed` 文件把候选实现误写成硬约束，全文使用：

| 词 | 效力 |
|---|---|
| **MUST / 必须** | 不满足就不能通过对应 milestone |
| **SHOULD / 应该** | 默认采用；偏离时必须写 ADR、证据和回退 |
| **CANDIDATE / 候选** | 需要 spike、评测或许可检查后选择 |
| **DEFERRED / 后置** | 明确不进入当前 milestone |

核心术语：

- **canonical**：唯一可写的业务事实来源；projection/cache 可删除重建；
- **projection**：为 UI/搜索优化的派生读模型；
- **Run 不可变**：Run 的 identity、输入/版本/策略/预算快照和终态结果不可覆盖；
  执行中的当前状态是 Event 派生 projection，可以按合法状态机前进；
- **locator**：能重新回到来源具体位置的结构化定位；
- **external write**：写出 Nana canonical Workspace/scratch 之外；
- **PolicyGrant**：对一类满足 capability/参数/数据/目录/网络/预算/期限约束的
  Action 做项目级预授权；不是复用一次性 Approval；
- **Receipt**：实际 Action、授权来源、副作用、结果和撤销路径的不可变证明；
- **strong isolation**：至少满足隔离文件系统、最小进程权限、受控网络、资源限制、
  凭据不继承和可销毁环境；仅有 venv 不算；
- **同一结论范围**：关键方向、数量级和预先声明容差一致，不要求浮点逐位相同；
- **verified**：通过本文档指定的证据/测试门槛，不表示绝对无风险。

## 6. 当前项目状态

> [!warning] 不要误读
> 本文件集是**正式重构规格**，不是“新版已经实现”的声明。当前运行代码仍是
> `v0.2.0-alpha` 原型；下一实施入口是 [[11_首个纵向切片执行清单]]。

本次完成定义：

- 旧 Obsidian 方案有可恢复备份；
- 新规格部署到正式 Vault 位置；
- Codex 与 Claude 的已达成共识、条件共识和未完成会签均如实记录；
- 产品、功能、界面、架构、安全、版本、迁移、验收和下一步均有权威文档；
- 文档通过链接、矛盾、可行性、可执行性和外部读者检查。
