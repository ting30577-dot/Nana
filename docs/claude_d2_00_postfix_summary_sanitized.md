# Nana D2-00 补丁后状态（脱敏）

已补充的关键点：

- `LocalSession.token` 已从裸字符串收敛为 secret 包装值；`repr()`、`str()`、`format()`、`asdict`、JSON 序列化、logging 和 traceback 路径都已测试不输出明文 token。
- SSE 仍使用真只读连接。
- `approval_authorizes` / `policy_grant_matches` 仍要求 Registry entry；安全 schema 校验、UTC 时间、一次性 Approval、v2 迁移和 append-only / retain-only 触发器均已保留。
- 当前 `openapi.json` 仍以 D0 `create_app()` 为源，这是有意保持现有契约基线；运行时 SSE 路由仍由单独 runtime app 处理。

最新验证：

- `python -m compileall nana_sidecar tests scripts` 通过
- `python -m unittest` 通过，206 tests

当前设计取舍：

- `effect_violation` 仍保持布尔审计位，未在 D2-00 中扩展为更细粒度枚举。
- `Approval.allowed_uses` 仍是定义性的一次性约束，多次授权由 `PolicyGrant` 承担。

请复核：在这些补丁后，是否仍有必须阻断 D2-00 的问题？若没有，请给出 ACCEPT；若仍有，请只列最小必改集合。 
