# Nana D2 权威 Vault 11/12 同步审查响应（脱敏）

## Claude 首审

- 11 号追加：`ACCEPT（附必须修改项）`。
- 12 号追加：`尚未达成共识`。
- 阻塞：F10 被两个不同问题复用；50 canary 与 360/100 的集合关系未定义；
  “七模块 55 tests”没有列出七个模块。

## Codex 处理

Codex 接受三个反例并修正：

1. Windows suspended Job 绑定反例保持为 Claude F6；F10 只表示 durable registry/
   digest 证据链。退出审查的额外问题改用 R1-R5，避免复用 F 编号。
2. 460 个执行场景明确分解为：200 path/parameter、50 credential canary、
   50 Approval/Grant、30 cancel/process-tree、30 malicious/oversized Artifact，合计
   360 D2-effective；100 prompt-like args containment 是 supplemental，不计入 360。
   canary 只证明当前 child env/stdout/stderr 边界，不代表完整 Prompt/log/export gate。
3. 55 tests 明确来自七个模块：capability admission、run scheduler、locked executor、
   budget accounting、security corpus、security matrices、runtime handoff。

## Claude 二审

- 11 号追加：文本层面 `ACCEPT`。
- 12 号追加：文本层面 `conditional ACCEPT`。
- 三个原阻塞已经关闭。
- 唯一剩余条件：不能继续仅以历史命名的 D0 manifest 作为 D2 权威入口；应提供
  自解释的 D2 manifest，并确认相对路径、fixture、SHA-256 与测试数字。

## 最终处理

Codex 新增独立的 `docs/evidence/v0.3.0-dev-d2-manifest.txt` 与对应 `.sha256`，保留
旧 D0 manifest 的历史路径。D2 manifest 固定 D2 退出时的完整可重放文件集合；本次
Vault 同步 packet/response 作为事后同步记录单独保留，不反向改写 D2 exit snapshot。

随后向 Claude 提供 D2 manifest、digest、security fixtures、退出摘要与严格警告测试
输出的脱敏文件级证据，请其完成最终收敛判定。

## Claude 最终文件级审查

- 11 号追加：`ACCEPT`。
- 12 号追加：`ACCEPT`，但要求把“30 cancel/process-tree 场景与 30 个真实孙进程
  fixture 是同一组”直接写入 Vault，避免独立读者误算成 60。
- Claude 逐项点数确认 manifest 102 条、手工 corpus 23 条、
  `200+50+50+30+30=360`、`360+100=460`，并确认 prompt/canary、窄执行面与 D3
  前置义务的文本边界一致。
- Claude 明确其无法在服务端重算本地 SHA-256 或重跑 55/68/269 tests；这些数字由
  Codex 本地复算，Claude 对其做跨文件静态一致性核对。

Codex 接受最后一项要求，已把同组/非双计说明和证据强度边界写入 12 号拟追加正文。
最终决策：11 号 `ACCEPT`；12 号 `ACCEPT`。

## Vault 写入验证

- 两个目标文件均与审查后的完整暂存副本逐字节一致。
- 写入后的文件仍以写入前原文件的完整 bytes 为前缀，只在末尾追加；11 号旧正文
  后新增 3,734 bytes，12 号旧正文后新增 6,432 bytes。
- 11 号新增标题位于第 770 行；12 号新增第 17 节位于第 749 行。
- 写入后 SHA-256：11 号
  `e0a893f0a94d92db3d961c51c9637c1d501b25b1cc28647b7c83ef2d3cf388aa`；12 号
  `72f5c8e29704df3f3b88f5d755b58faf9c4b7604b21f02a070bbf21a6aebcc7e`。
