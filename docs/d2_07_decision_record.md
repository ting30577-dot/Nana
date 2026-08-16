# Nana D2-07 决策记录

## 最终扫描结论

Codex 先后 VETO 了两次过早的本地退出结论：第一次逐项扫描得到 F1-F9；第二次把 23 项基础 corpus 对照权威规格，发现数量门槛不足。所有已发现问题均逐项修复并重新扫描。

Claude 服务恢复后先完成首轮实质复审：F2/F3/F9/F10/F11 ACCEPT；F1/F4/F5/F7 conditional ACCEPT；F6/F8 尚未共识。Codex 接受 F6/F8 反例并 VETO 对应旧实现/旧证据，完成修复后再次送审。Claude 二审对 F1/F4/F5/F6/F7/F8/F10 全部 ACCEPT，并明确 D2-07 可以共同 ACCEPT、没有剩余 D2 blocker。

## 关键决策

| 决策 | Codex | Claude | 当前状态 | 证据 |
|---|---|---|---|---|
| D2RuntimeHandoff v3 固定状态与审计语义 | ACCEPT | ACCEPT | ACCEPT | v3 明确 orphaned reservation、cancel projection、observed effects advisory。 |
| durable authorization material/Event binding | ACCEPT | ACCEPT | ACCEPT | schema v6 append-only `action_authorizations`；v4→v6 pinned digest。 |
| running cancel 与 orphaned 结算 | ACCEPT | ACCEPT | ACCEPT | Receipt/usage 原子记录、reservation 释放、Run quarantine。 |
| Windows process tree | ACCEPT；VETO taskkill 及 Popen 后绑定两版旧方案 | ACCEPT | ACCEPT | suspended-create→bind→resume；30 个真实孙进程 fixture。 |
| D2-06 矩阵有效性 | ACCEPT；VETO “460=完整 stable gate”旧表述 | ACCEPT | ACCEPT | 360 D2-effective +100 supplemental；22 authorization 与 7 artifact 精确 reason family。 |
| args Artifact persisted size/budget | ACCEPT | ACCEPT | ACCEPT | admission/executor 双入口与 structured errors。 |
| D3 不得重新推导授权或绕过 D2 执行 | ACCEPT | 未异议 | ACCEPT | handoff consumer rules。 |
| Workspace lock 是真实 mutation serving 前置门槛 | ACCEPT | ACCEPT（只阻塞 D3 mutation） | ACCEPT | handoff preflight 与权威 D0/D1 约束。 |

## 本地退出边界

D2 本地实现只证明受信 frozen unittest 的窄执行面，不是任意 hostile-code sandbox。D3 可以继续只读 UI、fixture/replay 和合流设计；在 Workspace lock、第二实例与 ready-order 门槛完成前，不得开放真实写入服务。

最终共同结论：D2-00 至 D2-07 在“受信 frozen worker 当前窄执行面”的口径下 ACCEPT。完整验证与 deferred stable/D3 门槛记录在 `docs/d2_07_exit_review.md`。
