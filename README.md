# AlgoMind

AlgoMind 是一个面向 AI/CS 方向学习者的桌面学习工作台。它把算法模式学习、刷题复盘和论文知识管理放在同一个持续生长的产品里。

> 当前阶段：`v0.1` — PySide6 桌面框架与滑动窗口可视化。

## 产品方向

- **算法工作台**：按解题模式组织算法，结合场景、代码、复杂度和动画理解状态变化。
- **刷题追踪**：记录 LeetCode 题目，并按算法模式统计和复盘。
- **论文库**：在同一工作台中完成论文整理、PDF 阅读、结构化笔记和进度管理。
- **知识图谱**：后期连接算法模式、题目经验与论文知识点。

AlgoMind 不是面向零基础用户的算法教程，而是认真学习者的个人研究环境。

## v0.1 范围

- 1280 × 800 可调整主窗口
- VS Code 风格侧边导航
- 算法模式列表
- 固定滑动窗口演示
- 开始、暂停、重置、单步与速度控制
- 论文库、刷题追踪、知识图谱和设置占位页

论文管理、数据持久化和完整刷题记录将在后续版本实现。

## 快速开始

要求 Python 3.11 或更高版本。

```bash
python -m venv .venv
```

Windows：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

macOS / Linux：

```bash
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 项目结构

```text
.
├── main.py
├── requirements.txt
├── algorithms/
│   └── sliding_window.py
├── ui/
│   ├── main_window.py
│   ├── sidebar.py
│   └── algo_workspace.py
├── visualizer/
│   └── array_canvas.py
├── assets/
│   └── icons/
└── docs/
    └── project_overview.md
```

## 开发原则

1. MVP 优先，每个版本只实现能够形成闭环的功能。
2. README 先于代码，版本目标保持明确。
3. 算法状态生成、可视化和界面交互彼此分离。
4. 每个功能完成后形成清晰、可回溯的提交。

完整产品规划见 [项目全景文档](docs/project_overview.md)。

## License

[MIT](LICENSE)

