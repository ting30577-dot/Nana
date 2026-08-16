# Codex × Claude 对等协作

Nana 把 Claude 接入为独立、只读、平等的共同设计者，而不是 Codex 的下级
评审者，也不是可自行修改项目的自治 Agent。重要决策使用同一份证据包，先由
Codex 和 Claude 分别独立提案，再完整交换提案和论据、互相反驳，最后进行显式
收敛。任何一方的重要异议未解决，都必须记录为“未达成共识”，不得包装成共识。

这里交换的是可审查的结论、假设、证据、风险和反驳摘要，不声称读取或公开任一
模型不可见的内部思维链。

## 配置：中转站是唯一通道

Nana 的 Claude 协作**只允许**走已配置的 Anthropic 兼容中转站。`scripts/ask_claude.py`
调用 `nana_core.ai.ClaudeReviewer`；适配器只读取 `NANA_CLAUDE_*`，缺少中转站配置
就直接失败，绝不会回退到官方 Anthropic API，也不会发起 OAuth、官方 API Key
或其他授权请求。新对话如果要求你授权官方服务，应立即停止，不要授权；先检查
下面三个变量和本文件。

以 WawAPI 为例，中转站的 Key 与官方 Key 分开保存：

```powershell
setx NANA_CLAUDE_API_KEY "你的中转站 API Key"
setx NANA_CLAUDE_BASE_URL "https://wawapi.top"
setx NANA_CLAUDE_MODEL "claude-sonnet-4-6"
```

设置后关闭当前终端，再重新打开。官方 Anthropic SDK 只是本地兼容客户端，实际
请求地址由 `NANA_CLAUDE_BASE_URL` 决定，例如
`https://wawapi.top/v1/messages`；这不等于直连官方 Anthropic。Base URL 不需要
手动添加 `/v1`。
如果中转站后台给出的模型名称不同，以后台模型列表为准。

不要设置或转发 `ANTHROPIC_API_KEY`。即使它存在，Nana 适配器也会忽略它；删除
`NANA_CLAUDE_API_KEY` 或 `NANA_CLAUDE_BASE_URL` 后，程序会拒绝请求，而不是改走
官方接口。

### 调用前检查

```powershell
Get-ChildItem Env:NANA_CLAUDE_API_KEY,Env:NANA_CLAUDE_BASE_URL,Env:NANA_CLAUDE_MODEL
```

只检查变量是否存在和 Base URL 是否为中转站，不要把 Key 值复制到聊天、上下文
文件、日志或命令行参数中。

## 发起一次讨论

默认会把 `README.md` 和 `docs/project_overview.md` 作为背景：

```powershell
.\.venv\Scripts\python.exe .\scripts\ask_claude.py "Nana 下一步应该优先验证什么？"
```

这条命令是唯一推荐入口。不要直接运行官方 Claude CLI、官方 SDK 示例或任何会
要求 `ANTHROPIC_API_KEY`/OAuth 授权的命令。

`docs/evidence/*claude-cli-preflight*` 和 `*claude-cli-result*` 只是历史上的
一次性隔离实验记录，不是当前调用路径；不要按其中的 OAuth/first-party 步骤
重试，也不要因为其中的历史授权边界再次向用户索取授权。当前产品负责人已经
授权指定脱敏包经 Nana 中转站发送，连接失败只应由 Codex 诊断并记录。

评审具体代码时，可以重复传入 `--context`：

```powershell
.\.venv\Scripts\python.exe .\scripts\ask_claude.py `
  "这个仓储层设计有哪些一致性风险？" `
  --context .\nana_core\research\repository.py `
  --context .\tests\test_research_repository.py
```

Claude 只返回设计意见和 token 用量，不获得文件写入能力。重要议题至少经过：

1. 同证据包下的独立提案；
2. 双方提案与决策依据的完整交换；
3. 双向反驳；
4. 带明确异议项的收敛审议。

用户负责决定产品目标和不可替代的个人偏好；事实、技术和路线判断不应因为某个
模型先发言就自动服从它。
