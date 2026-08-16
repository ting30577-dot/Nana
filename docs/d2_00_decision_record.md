# Nana D2-00 决策记录

## 阶段结论

D2-00 完成 authorization/storage hardening，不进入 scheduler 或真实执行。Codex 与 Claude 历史共同审查结论为 conditional ACCEPT，后续 D2-01 至 D2-07 已把条件逐项落成并再次扫描。

| 扫描项 | 最终处理 | 状态 |
|---|---|---|
| Capability identity | `CapabilityRef` 强制 id/version/digest；registry truth 覆盖 executable 与 contract digest | ACCEPT |
| 授权来源 | Approval/PolicyGrant 必须匹配完整 registry、args/effects/provider/risk/budget/time | ACCEPT |
| safe schema | 独立 safe JSON Schema 子集，未知/危险 keyword 失败关闭 | ACCEPT |
| one-time Approval | `allowed_uses=1`，后续 D2-03b 原子 consumption/replay 拒绝 | ACCEPT |
| Receipt/effects | 保存 authorized/actual effects；越界必须 `effect_violation=true` 且 `effect_unknown` | ACCEPT |
| locator privacy | URL credentials、敏感 query、非 portable local ref 均拒绝 | ACCEPT |
| storage durability | Event append-only、outbox retain-only、高 schema readonly preflight | ACCEPT |
| 后续兼容 | schema v6 authorization snapshot、executor Receipt、handoff v3 均沿用 D2-00 contract | ACCEPT |

Claude 最终二审对 F7 明确 ACCEPT：handoff v3 已把 worker observed-effect self-report 降为 advisory，真正的阻断不依赖该报告。D2-00 最终状态为共同 ACCEPT。
