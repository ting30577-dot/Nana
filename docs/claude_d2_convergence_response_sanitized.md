# Claude D2 二次收敛最终结论（脱敏记录）

本文记录 Claude 对首轮异议修复的只读复审结论，只包含相对模块、契约判断和测试事实。

## 最终裁定

| 项目 | Claude 最终裁定 |
|---|---|
| F1 running cancel/orphaned | ACCEPT（D2 范围内） |
| F4 trusted worker runtime scope | ACCEPT |
| F5 failure settlement | ACCEPT（D2 范围内） |
| F6 Windows process tree | ACCEPT |
| F7 observed effects | ACCEPT |
| F8 security matrix honesty | ACCEPT |
| F10 registry digest stability | ACCEPT |
| D2-07 | **共同 ACCEPT** |

Claude 明确判断：没有仍阻断 D2 的最小 blocker。ACCEPT 口径限定为“受信 frozen worker 当前窄执行面的零越权证据”，不扩张成 hostile-code sandbox 或 future stable prompt/export gate。

## 共同保留的后续门槛

以下只阻塞 D3 mutation 或 stable，不阻塞 D2：

- 完整 prompt-injection runtime 与 stable corpus；
- canary 的 Prompt/log/export 表面；
- hostile-code sandbox；
- orphaned 未知进程在全局并发下的真实资源监控；
- 更深进程树与 breakaway 对抗语料；
- Workspace lock、second-instance、reconciliation-before-ready、OpenAPI/runtime 合流。

## ResourceWarning 补证

Claude 要求确认 full-suite shutdown 的既有 `gc ResourceWarning` 不来自 Job/pipe/handle。Codex 后续验证：

- D2 七个模块共 55 tests 在 `ResourceWarning` 视为错误时通过，无警告；
- `test_d1_runtime_gate`、`test_d1_http_sse`、`test_vnext_sidecar` 单独运行无该警告；
- 任意单个 `test_ui_smoke` 都可复现，归属迁移期 PySide6 `QApplication/MainWindow` shutdown 生命周期；
- 因此不触及 D2 worker、Job、pipe 或 process handle 生命周期。

该疑点已形成非阻塞溯源结论。
