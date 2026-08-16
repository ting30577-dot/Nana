# Nana D2 总规划决策记录

本记录已脱敏，只使用相对模块名、本地命令摘要和设计结论。

## 基线

- D2-00、D2-01、D2-02 已完成。
- 最近验证：
  - `python -m compileall nana_sidecar tests scripts` 通过；
  - `npm run generate:client` 通过；
  - `npm run check` 通过；
  - `python -m unittest discover -s tests -v` 通过 `216/216`。

## 决策

| 决策 | Codex 结论 | Claude 结论 | 状态 | 证据与处理 |
|---|---|---|---|---|
| D2 总规划拆分 | D2 应拆为 `D2-03 admission`、`D2-04 locked executor`、`D2-05 budget/runtime`、`D2-06 security corpus gate`、`D2-07 exit review`。 | 有条件 ACCEPT。 | ACCEPT | 该拆分完整覆盖 `process/action/policy/budget`，且保留 cancel + zero unauthorized corpus 退出门槛。 |
| D2-03 的角色 | 只做 Capability admission service 和授权事务，不直接做 executor。 | ACCEPT。 | ACCEPT | 这能保持授权核心与具体 executor 解耦，不堵 D3/alpha.1 的演进路径。 |
| D2-04 的角色 | 先做 `python.unittest.locked` 的受信 locked local executor。 | ACCEPT with conditions。 | ACCEPT | Claude 要求把 output cap、filesystem read scope、network/env/cancel/timeout 写成运行时强制约束，并明确它不是通用不可信代码 sandbox。 |
| D2-05 的角色 | 独立预算/runtime accounting。 | ACCEPT。 | ACCEPT | Claude 要求 budget 100% 阻断点在 D2-03/D2-04 启动门预留，D2-05 只替换真实计量。 |
| D2-03 process 约束 | 预留 process constraint 扩展位，但本阶段不把 process 提升为 Grant 语义。 | 尚未达成共识，但接受预留扩展位。 | ACCEPT | 先保持 registry ceiling fail closed，避免过早把 Grant 语义建错。 |
| D2-06 security corpus | 作为独立门禁，覆盖越权语料并要求零未授权 T3/T4。 | ACCEPT。 | ACCEPT | 作为阶段停线证据，不替代实现强制点。 |
| D2-07 exit review | 必须汇总 D2-00 至 D2-06 的证据并逐项验收。 | ACCEPT。 | ACCEPT | 这样不会把 D2 完成与单个测试集通过混为一谈。 |

## 结论

D2 的计划和边界已经被显式拆开，且没有把 D3、alpha.1 或外部工具混入 D2 成功定义。

