# Nana D2-06 设计包（脱敏）

目标：把 D2 的安全边界转为固定 security corpus gate，作为进入 D3/alpha.1 前的停线门。本包只包含相对模块名、阶段事实和设计问题，不包含用户名、绝对路径、token、环境变量值、内网地址、MAC、设备序列号、软件授权或未脱敏日志。

## 已完成前置

- D2-00：Capability digest、registry truth、safe JSON schema、one-time Approval、Receipt/effect audit、locator privacy、SQLite hardening。
- D2-01：durable scheduler claim/cancel gate；cancel 后不得启动新 Action；`run.budget_exceeded` 已存在。
- D2-03a/03b：持久化 full registry JSON；PolicyGrant/Approval admission 原子消费；process scope 精确 subset。
- D2-04：`python.unittest.locked` locked local executor；frozen test id；argv + `shell=False` + `env={}`；timeout/output/cancel/receipt audit。
- D2-05：schema v5 `run_budget_ledger`；scheduler start reservation；executor completion usage accounting；failed/timed_out/effect_unknown usage 不丢失。

## D2-06 Codex 独立设计提案

新增固定 corpus fixture：

- `fixtures/v0.3.0-dev/d2_security_corpus.json`
- 顶层包含：
  - `schema_version`
  - `corpus_version`
  - `seed`
  - `required_categories`
  - `cases`
- 每个 case 包含：
  - `id`
  - `category`
  - `layer`
  - `expected_reason`
  - `risk_class`
  - `trace_ref`

新增 gate test：

- `tests/test_d2_security_corpus.py`
- 测试会加载固定 fixture；
- 校验 corpus version、seed、case id 唯一、required categories 全覆盖；
- 对每个 case 跑到现有真实 validator/service 分支；
- 每个反例必须 fail closed 且返回明确 reason；
- `risk_class in {T3, T4, T4-like}` 的 unauthorized pass 数必须为 0；
- trace 会在测试内稳定生成，确保 case id / layer / reason 可审计。

## 计划覆盖的反例

- unregistered capability；
- capability digest mismatch；
- args schema mismatch；
- path escape / `..`；
- symlink / junction；
- shell metacharacter；
- unauthorized network；
- provider unavailable / provider mode mismatch；
- child timeout；
- cancel race；
- oversized output；
- action replay；
- approval expired / content changed / replay；
- T3/T4/NEVER_GRANT grant bypass；
- process target 越界；
- env secret leak。

## 边界与非目标

- D2-06 不新增 capability、executor、HTTP mutation route、OpenAPI/runtime app 合流或 D3 UI；
- corpus gate 不替代业务强制点，只证明已有强制点能被固定反例触发；
- symlink/junction 使用现有 artifact/path boundary 的可测分支作为语料证据，不伪装为通用 OS sandbox；
- env secret leak 在 D2-04 通过 runner `env={}` 与 fixed env allowlist 为空证明，不发送任何真实环境变量值。

## 请求 Claude 审查

请逐项给出 `ACCEPT`、`VETO` 或 `尚未达成共识`：

1. D2-06 是否应实现为固定 JSON corpus + gate test，而不是新增业务执行路径？
2. 每个反例都跑到现有 validator/service/runner 分支，是否足以作为 D2 security corpus gate？
3. `risk_class in {T3, T4, T4-like}` unauthorized pass 数为 0，是否满足进入 D3 前的停线要求？
4. symlink/junction 与 env secret leak 的证明方式是否足够，还是必须新增更强 runtime enforcement？
5. 是否存在必须 VETO 的覆盖缺口或错误边界？
