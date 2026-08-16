# Nana 项目全景

> 当前实现：`v0.2.0-alpha` 可运行遗留原型
> 正式方向：`v0.3.0` 全量重构规格
> 更新日期：2026-07-29

Nana 的正式定义已经从“算法/方法学习工具”收敛为：

> local-first、证据可追溯、高自治的个人 Research & Engineering OS，把真实科研或
> 工程问题推进为可验证结论、可复现实验、可复用工件和可证明能力。

唯一主循环是：

```text
目标/问题
→ 研究与证据
→ 假设与可编辑计划
→ 实现与实验
→ 比较与反证
→ 用户确认的 Decision 与交付
→ 跨项目复用
```

Algorithm Investigation、Paper/Repo Reproduction、Engineering Optimization
是三种共享统一 Runtime 的 Plan Template。Action、PolicyGrant、Approval 和 Receipt
共同表达受限自治；能力成长由真实 Project/Run/Artifact/
Decision 证据派生，不再成为独立游戏化主循环。

## 当前与目标的边界

| 维度 | 当前 `v0.2.0-alpha` | 目标 `v0.3.0` |
|---|---|---|
| UI | PySide6、列表/详情/CRUD | Research Cockpit + Research Studio |
| 前端 | Python/Qt | React/TypeScript |
| 桌面壳 | PyInstaller | Web spike 通过后验证 Tauri 2 |
| 后端 | UI 与业务紧耦合 | Python 3.12 FastAPI sidecar |
| 数据 | legacy SQLite objects | canonical SQLite + Artifact Store |
| 执行 | 预置方法表单 | Plan/Run/Event/Approval runtime |
| AI | 只读共同设计 adapter | Capability/Policy/Budget 约束的高自治 |
| 证据 | 手工对象 | locator/provenance/引用一致性 |
| 实验 | legacy Experiment | 不可变 Run、环境/代码/输入/指标/产物 |
| 发布 | 原型打包 | 迁移/恢复/安全/Windows 数据不变性门槛 |

旧 PySide6 UI 和 legacy schema 冻结；纯算法函数、测试和已验证 adapter 可选择性
复用。新旧产品不长期双写。

## 权威规格

完整规格位于：

- [Nana vNext 总览](../obsidian_export/Nana_研究系统_vNext/00_Nana_总览与导航.md)
- [联合产品宪章](../obsidian_export/Nana_研究系统_vNext/01_联合产品宪章.md)
- [对标平台与版本演进](../obsidian_export/Nana_研究系统_vNext/02_对标平台与版本演进.md)
- [用户旅程与功能系统](../obsidian_export/Nana_研究系统_vNext/03_用户旅程与功能系统.md)
- [界面重构与交互规范](../obsidian_export/Nana_研究系统_vNext/04_界面重构与交互规范.md)
- [技术架构与数据契约](../obsidian_export/Nana_研究系统_vNext/05_技术架构与数据契约.md)
- [AI 自治、安全与隐私](../obsidian_export/Nana_研究系统_vNext/06_AI自治_安全与隐私.md)
- [版本路线图与验收门槛](../obsidian_export/Nana_研究系统_vNext/07_版本路线图与验收门槛.md)
- [迁移、备份、发布与恢复](../obsidian_export/Nana_研究系统_vNext/08_迁移_备份_发布与恢复.md)
- [Codex/Claude 对等决策记录](../obsidian_export/Nana_研究系统_vNext/09_Codex_Claude对等决策记录.md)
- [完整性、可行性、可执行性终审](../obsidian_export/Nana_研究系统_vNext/10_完整性_可行性_可执行性终审.md)
- [首个纵向切片执行清单](../obsidian_export/Nana_研究系统_vNext/11_首个纵向切片执行清单.md)

冲突时，以该规格中标记 `confirmed` 的决定和最终审计为准。当前代码能运行不等于
目标架构已经实现；任何未通过 spike/测试的能力都保持 `implementation-gate`。
