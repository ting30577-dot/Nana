# Nana

Nana 是一个 Windows 优先、本地优先的个人科研与工程工作台。当前仓库版本为
`v0.3.0-dev`。

- 产品原则：[项目内核](docs/PROJECT_KERNEL.md)
- 当前工程状态：[活动状态](docs/ACTIVE_STATE.json)
- 已冻结的 D3 基线：[D3 权威说明](docs/CURRENT_D3_AUTHORITY.md)

## 当前状态

当前版本已经完成：

- React + FastAPI 的 D3 浏览器纵向切片；
- 本地 Workspace、受控运行、证据与产物关系；
- 暂停/继续、失败后重试关系；
- 需要授权的草稿导出与 Receipt；
- Tauri Stage 1 静态 Windows 壳及受保护 CI。

Tauri Stage 1 只证明桌面壳能够安全加载本地前端资源。它没有启动 Python
sidecar，也没有接管产品数据，更不是正式安装包。当前产品迁移状态仍为
`false`。

## 现在可以看到什么

| 入口 | 可以看到 | 定位 |
|---|---|---|
| D3 本地 Web 界面 | 当前 React 工作台、开发态研究旅程、运行状态、证据、产物和受控导出 | 当前新界面的主要观察入口 |
| PySide6 桌面界面 | 旧版科研对象、算法演示和可视化 | 冻结的兼容与回滚入口，不再增加新功能 |
| Tauri 静态壳 | Windows 桌面窗口中的本地 React 静态资源 | 技术验证，不具备真实后端工作流 |

当前版本仍是开发基线，不是日常使用完成品。目前没有签名安装包、Tauri
sidecar 生命周期、桌面原生目录选择、自动更新或旧数据产品迁移。

## 推荐体验：D3 本地 Web 界面

先构建前端，再启动本地认证启动器：

```powershell
Set-Location .\nana_web
npm.cmd ci
npm.cmd run build
Set-Location ..
.\.venv\Scripts\python.exe .\scripts\run_d3_dev_journey.py
```

启动器会使用系统分配的本地端口并打开浏览器。默认 Workspace 位于 Windows
的 Nana 用户数据目录，不写入源码目录。导出时需要选择一个已经存在、专用且为空的
本地目录。

## 旧版桌面入口

旧版 PySide6 程序仍可运行，用于兼容、比较和回滚：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

该界面和旧 SQLite 结构已经冻结，不代表当前目标界面。

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 旧版 Windows 构建

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

输出位于 `dist\Nana\Nana.exe`。这是旧版兼容构建，不是 Tauri 正式发行版。

## 开始一个 Nana 开发任务

不要先扫描整个仓库或整个 Obsidian Vault。按照 `AGENTS.md` 和项目 skill 选择一个
有边界的 route：

```powershell
python .\scripts\nana_context.py check
python .\scripts\nana_context.py bootstrap --route governance
```

可用 route 位于 `config/context-routes.json`。

## 仓库结构

```text
.
├── main.py                 # 冻结的旧版桌面入口
├── algorithms/             # 可复用算法资产
├── db/                     # 旧版 SQLite 实现
├── ui/                     # 冻结的 PySide6 界面
├── visualizer/             # 旧版可视化
├── nana_sidecar/           # 当前 Python 业务运行时
├── nana_web/               # 当前 React 界面
├── src-tauri/              # 已验证的静态 Windows 壳
├── tests/                  # 可执行契约与回归测试
└── docs/                   # 当前权威状态、决策与最小证据
```

## 许可证

[MIT](LICENSE)
