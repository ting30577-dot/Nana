这些问题不需要你逐项做产品选择。它们大多是 D3-07 为落实既定安全边界而产生的技术决策，可以直接依据现有计划裁定。

结论：整体方案方向正确，但不能原样全部确认。其中第 1、6、7 项需要精确修正，第 9 项的“15 分钟”不合理；第 2 项还缺少本地固定磁盘和云同步目录限制。

## 逐项裁定

| # | 裁定 |
|---|---|
| 1. 原子替换探针时机 | 有条件确认 |
| 2. 导出目录限制 | 确认，但增加限制 |
| 3. Export Run Relation 图 | 确认 |
| 4. 浏览器导出申请 | 确认 |
| 5. 拒绝/过期后的 Run | 确认 |
| 6. draft-report 格式 | 有条件确认 |
| 7. selection 存储 | 有条件确认 |
| 8. Windows 目录身份 | 确认 |
| 9. selection 有效期 | 不确认 15 分钟，改为 60 分钟 |
| 10. D3 真实选择入口 | 确认 |
| 11. 重启收敛 | 确认，但补充 write fence 前置条件 |
| 12. 内存与 SQLite 协调 | 确认，但不得称为原子事务 |

## 1. 原子替换探针

确认以下顺序：

```text
目录选择阶段
→ 只读身份与资格检查
→ 创建 Export Run/Action/Approval
→ 用户批准
→ 原子提交授权与一次性消费
→ 持久化 first-write fence
→ 执行真实原子替换探针
→ 探针通过后写 draft report
```

必须修正截图中的一句话：

> “探针失败则记录失败 Receipt”不能覆盖所有失败情况。

正确分类是：

- 探针尚未产生任何外部字节就失败：`failed`，actual effects 为空；
- 探针产生过文件，但已确定清理且目录状态可验证：`failed`，Receipt 记录实际探针效果；
- 写入开始后发生崩溃、残留无法确认或清理结果无法证明：`effect_unknown`；
- 绝不回退到非原子写入；
- `effect_unknown` 不允许自动重试或重新绑定目录。

这符合 D3 的“未批准零副作用”和“写入不确定则诚实标记”原则。

## 2. 导出目录限制

确认 D3 只使用专用、已存在、空的测试目录，而且该规则只适用于 `v0.3.0-dev` 的 T3 fixture，不自动升级为未来所有导出功能的永久规则。

必须拒绝：

- 卷根目录；
- 用户主目录本身；
- Windows、Program Files、ProgramData 等系统/程序目录；
- Nana 安装目录、状态目录、缓存、备份目录；
- Workspace 本身、其祖先或后代；
- symlink、junction、mount point、任意 reparse component；
- SUBST、短路径、大小写或其他方式形成的身份别名；
- UNC、网络映射盘；
- OneDrive、Dropbox 等已知云同步目录；
- 不受支持或身份不可稳定验证的文件系统；
- 非空目录；
- 已存在同名目标文件；
- 选择后、写入前发生身份或内容变化的目录。

其他规则：

- 仅使用固定文件名；
- 不允许覆盖；
- 目标碰撞立即失败；
- 写入前重新检查目录为空、身份不变；
- 判断依据必须是句柄和文件系统身份，不能只是字符串前缀。

这比截图更符合“controlled local export、无远程发布、无覆盖”的既定范围。

## 3. Export Run 的 Relation 图

确认不扩展 Relation Registry，采用现有关系：

```text
算法 Run
  ├─ run_produces_finding → Finding
  └─ run_produces_artifact → test-result Artifact

Export Run
  └─ run_produces_artifact → draft-report Artifact

draft-report Artifact
  └─ artifact_derived_from_artifact → test-result Artifact
```

同时在 Export Run snapshot 中冻结：

- Finding ID、revision、内容承诺；
- 算法 Run ID 和终态；
- 源 Artifact ID/hash；
- draft Artifact ID/hash；
- renderer version/digest；
- capability digest；
- selection identity digest；
- 预算、effects 和输出限制。

不应伪造：

- Export Run → Finding 新 Relation；
- Export Run → 算法 Run 新 Relation；
- `run_retry_of_run` 等语义不符的关系。

这是 D3 最小闭环，未来真实发现关系缺口后再扩 Registry。

## 4. 浏览器导出申请

确认。

浏览器只提交：

```text
RequestApproval {
  command_id
  finding_id
  expected_revision
  target_selection_id
}
```

服务端必须派生：

- 算法 Run；
- test-result Artifact；
- draft-report Artifact；
- Export Run；
- Export Action；
- capability；
- ActionHash；
- 内容 hash；
- selection identity digest；
- requested effects；
- Approval subject；
- 预算与风险。

浏览器不得提交：

- 文件路径；
- 文件名；
- 原始 bytes；
- Run/Action ID；
- capability ID；
- hash；
- 风险等级；
- effect；
- 授权来源。

这里可以增加一个窄的 journey/application request 形状，但不新增平行的 canonical Command；内部组合现有 `StartRun`、`ProposeAction`、`CommitArtifact`、`RequestApproval` 语义。

## 5. 拒绝或过期后的 Export Run

确认。

`DecideApproval(denied)` 事务只负责：

- Approval 变为 denied；
- `approval.decided` Event/outbox；
- 稳定 CommandResult。

它不能在同一个事务中修改 Run，也不能授权、消费或产生 Receipt。

提交后，由确定性的系统 `CancelRun`：

- 取消等待审批的 Export Action；
- 终结 Export Run；
- 使用固定 causation/correlation 和确定性 command ID；
- 响应丢失或进程重启后可幂等重放。

Approval 过期采用相同收敛路径：

```text
approval.expired
→ 系统 CancelRun
→ Export Action/Run cancelled
```

中间发生崩溃时，启动 reconciliation 必须补齐 `CancelRun`，不能永久遗留 running Run。

## 6. draft-report Artifact

格式总体确认，但不能依赖“自动脱敏”把任意敏感字段变安全。

正确规则是：

- 只接受已被 canonical data policy 标记为 `public` 的输入；
- 非公开、未知或混合数据直接拒绝导出；
- renderer 只读取明确允许的字段；
- 转义用于阻止 Markdown/HTML/link 注入，不作为隐私脱敏手段。

冻结格式：

- UTF-8，无 BOM；
- Unicode NFC；
- LF；
- 恰好一个结尾换行；
- 最大 4096 bytes；
- `text/markdown`；
- 固定模板和 renderer digest；
- 固定 `DRAFT` 标志；
- 50 个 export credential canary 零命中。

允许内容：

- public Inquiry question；
- public Finding statement；
- confidence basis；
- 成功算法 Run 的固定摘要；
- Action Receipt 的固定结果摘要；
- 源 Artifact ID/hash；
- 明确的 dev fixture scope。

禁止内容：

- 绝对或逻辑路径；
- 源 Artifact 原始内容；
- stdout/stderr；
- 环境变量；
- Provider、模型、凭据；
- URL 和外部链接；
- 任意用户 Markdown/HTML；
- 任意未列入模板的 metadata。

## 7. selection 的存储方式

确认“真实路径和目录句柄只存在进程内存”，但需要补充：

可以持久化的不是 selection 本身，而是不可逆、非定位性的授权承诺：

- `selection_identity_digest`；
- 固定目标文件承诺；
- expiry；
- ActionHash；
- Approval subject；
- Export Run/Action 绑定；
- Event aggregate version。

不得持久化：

- 原始绝对路径；
- 目录句柄；
- volume/file ID 明文；
- 能恢复原始路径的字段；
- opaque selection token 明文；
- 用户名或目录层级；
- 路径出现在 Event、CommandResult、Receipt、日志、OpenAPI 示例或审查包中。

进程或 LocalSession 重启后：

- 原 selection 永久失效；
- 不允许用新目录重新绑定旧 Action；
- 用户重新选择目录时必须创建新的 Export Run、Action 和 Approval 链。

## 8. Windows 目录身份验证

确认。

不能只使用：

```python
Path.resolve()
```

或：

```text
字符串前缀比较
```

必须至少包含：

- 逐级拒绝 reparse component；
- 打开并保留目录句柄；
- 获取最终规范化目录身份；
- 获取本地 volume/file identity；
- Workspace 和目标都使用句柄身份比较；
- 检查 Workspace 与目标不存在祖先/后代重叠；
- 防止选择后 rename/delete/replace；
- 写入前重新读取并比较身份；
- 固定子目标也通过受控目录句柄解析。

volume/file identity 只能用于本机进程内验证和不可逆 digest，不能进入浏览器、日志、导出或 Claude 审查包。

## 9. selection 有效期和次数

不确认“最长 15 分钟”。

原因是用户在 Web 服务启动前选择目录，随后还要完成：

```text
create → plan → run → finding → approval → export
```

15 分钟很可能在正常使用中提前失效，也与规划中的 30 分钟观察式旅程冲突。

D3 初始规则改为：

- 最长有效期：60 分钟；
- 同时受当前 LocalSession 生命周期约束；
- Approval expiry 不得晚于 selection expiry；
- 一个 selection 只能绑定一个 Export Run 和一个 Action；
- selection 一旦 reserved/bound，不能用于第二次请求；
- Action/Run 终态、过期、session 结束或应用 draining 时立即关闭；
- 每次重新导出必须重新选择目录；
- 后续根据真实 D3 使用时间调整，但不得放宽“一次性”和“会话绑定”。

## 10. D3 真实目录选择入口

确认。

D3 阶段：

- Nana launcher/CLI 在启动 Web runtime 前交互式询问目录；
- 不把路径放进普通命令行参数，避免出现在进程列表；
- runtime 验证后创建内存 selection；
- 浏览器只收到 opaque ID、脱敏目录叶名称和 expiry；
- 浏览器没有路径输入框；
- test harness 必须明确标记为 `test_harness`；
- harness 不能声称 `user_selected=true`；
- 不提前引入 Tauri。

Tauri spike 之后，native picker 只替换“目录选择来源”，后端 selection contract 不变。

## 11. 重启后的收敛规则

确认，但必须先冻结一条强约束：

> first-write fence 必须先在 SQLite 提交，之后才允许任何 probe 或外部写入。

否则“没有 fence 等于没有副作用”不成立。

收敛表：

| 持久状态 | 重启结果 |
|---|---|
| Approval 尚未决定 | expire Approval，系统 CancelRun，无外部效果 |
| Approval 已拒绝 | 补做幂等 CancelRun，无外部效果 |
| 已批准/消费，但无 first-write fence | Action failed，actual effects 为空，Export Run failed |
| 已 claim，但无 fence | 同上，释放预算一次 |
| 已存在 durable fence | `effect_unknown`，禁止重试和重新绑定 |
| Action/Run 已终态 | 只重放既有事实，不产生新副作用 |

如果任何实现路径可能先写文件、后写 fence，该实现必须 VETO。

## 12. 内存 selection 与 SQLite 协调

确认使用：

```text
reserve selection
→ SQLite 原子提交 Export subject / Event / outbox / CommandResult
→ finalize in-memory binding
```

但必须明确：

> 这不是内存和 SQLite 之间的跨资源原子事务，而是带补偿和故障收敛的协调协议。

规则：

- reservation 绑定 `command_id + request_hash + deterministic Run/Action IDs`；
- SQLite 回滚只释放完全匹配的 reservation；
- SQLite 成功后，同进程恢复可以 finalize；
- commit 后响应丢失，重放返回原 CommandResult，不创建第二套对象；
- commit 后进程崩溃，selection 消失，按第 11 项收敛；
- 不能因为 selection 消失而重新解释已有 CommandResult；
- 不能把新 selection 绑定到旧 Export Action；
- 所有 crash window 必须有故障注入测试。

## 最终可冻结版本

这 12 项可以收敛为：

- 第 1 项：接受，但修正失败分类；
- 第 2 项：接受并增加本地固定磁盘、云同步/网络目录限制；
- 第 3–5 项：接受；
- 第 6 项：接受，但用“public canonical input”代替“自动脱敏”；
- 第 7–8 项：接受并限制身份信息只能本机内存使用；
- 第 9 项：拒绝 15 分钟，改为 60 分钟、一次性、会话绑定；
- 第 10 项：接受；
- 第 11 项：接受，但 first-write fence 必须先于所有外部效果；
- 第 12 项：接受，明确为协调协议而非原子事务。

这些决定没有扩展 D3 的产品范围，都是为了完成既定的“审批后把无敏感 draft report 写入用户选择的 Workspace 外测试目录”这一条旅程。D3 总规划仍然要求 Claude 对 D3-07 安全 Gate 独立复核，因此本地设计可以据此冻结，但在共同 ACCEPT 及实现证据完成前，外部写入仍应保持关闭。
