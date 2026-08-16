# Nana D2 Vault 同步文件级复核证据（脱敏）

## D2 manifest

- 路径：`docs/evidence/v0.3.0-dev-d2-manifest.txt`
- 条目数：102
- 路径不存在或 SHA-256 不一致：0
- normalized manifest digest：
  `1cbb07d25a1333e0a860182f0a47f915601c90af083b6e8b9daf4ec5aedd7f5d`
- `docs/evidence/v0.3.0-dev-d2-manifest.sha256` 记录值与实际值一致。
- D2 manifest 是 D2 exit snapshot；本次事后 Vault 同步 packet/response 不纳入该
  snapshot，避免后续文档自引用或改写退出时证据。

## 严格警告回归

执行以下七个模块，并把 `ResourceWarning` 视为错误：

1. `tests.test_d2_capability_admission`
2. `tests.test_d2_run_scheduler`
3. `tests.test_d2_locked_executor`
4. `tests.test_d2_budget_accounting`
5. `tests.test_d2_security_corpus`
6. `tests.test_d2_security_matrices`
7. `tests.test_d2_runtime_handoff`

结果：`Ran 55 tests in 28.757s`，`OK`。

## Security matrix 文件事实

`fixtures/v0.3.0-dev/d2_security_matrices.json` 固定：

- `executed_scenarios=460`
- `d2_effective_scenarios=360`
- `stable_full_surface_gate_complete=false`
- path/parameter：200
- prompt-like args：100，`counted_in_d2_effective_scenarios=false`
- credential canary：50，仅 child env/stdout/stderr，完整 Prompt/log/export absent/deferred
- Approval/Grant：50
- runtime cancel/process-tree：30，`descendant_probe=true`，5 秒整树退出期限
- malicious/oversized Artifact：30

因此 360 = 200 + 50 canary + 50 Approval/Grant + 30 runtime cancel/process-tree +
30 Artifact；100 prompt-like args 是 supplemental。30 process-tree scenarios 与
30 个真实孙进程 fixture 是同一组，不是两组各 30。

## 其他退出证据

- 手工 corpus：23 项，version/seed/trace/evaluator/expected reason 固定。
- 最终聚焦回归：68/68。
- D2 exit 时全量回归：269/269。
- Python compileall、TypeScript `tsc --noEmit`、隐私扫描通过。
- `docs/d2_07_exit_review.md` 已把补充问题改用 R1-R5；F6 继续表示 Windows Job
  反例，F10 继续表示 durable registry/digest 证据链。

## 请 Claude 最终判定

请结合 D2 manifest、对应 `.sha256`、security fixtures、退出摘要和本文件，判断：

1. 11 号追加是否最终 ACCEPT；
2. 12 号追加是否最终 ACCEPT；
3. 若仍不能接受，只列文件级最小 blocker。
