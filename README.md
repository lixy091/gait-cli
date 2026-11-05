# Gait CLI

Gait 是一个最小的三阶段迭代工作流框架，包含两个相互解耦的目录：`gait-cli/` 是 Python 控制平面，负责状态机、命令、门禁和 OpenSpec 调用；`gait-engine/` 是纯 YAML、模板和文档组成的声明式资产，描述流程结构。业务项目通过 `.gait/project.yaml` 的 `engine_path` 指向引擎目录。

## 安装

要求 Python 3.10+。在本目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

macOS/Linux 激活方式为 `source .venv/bin/activate`。运行测试：`python -m pytest -q`。

## 初始化业务项目

在业务仓库根目录运行 `gait init --engine-path ../gait-engine`。命令会交互式选择 `claude` 或 `codex` runtime，生成 `CLAUDE.md` 或 `AGENTS.md`，创建 `.gait/` 配置和任务索引。engine_path 可随后配置：

```sh
gait config set engine_path ../gait-engine
gait config get engine_path
gait config set coding_agent codex
```

`gait init --tools` 支持 `auto`（默认）、`check`、`install`、`skip`。OpenSpec 是必装依赖：阶段一用其管理 change/artifacts，阶段三用 `openspec archive` 归档，不存在手写目录降级。`check` 只报告缺失；`skip` 跳过初始化检查，但之后 task init/close 若 OpenSpec 缺失会直接报错并显示安装提示。macOS/Linux 的交互式 `auto` 会逐项询问安装；`install` 授权直接安装 Node.js 24 与 OpenSpec。Windows 或无 TTY 时不自动安装，按提示手工安装或在 macOS/Linux 交互终端运行 `gait init --tools install`。Node 安装使用 nvm；OpenSpec 安装命令为 `npm install -g @fission-ai/openspec@latest`。

项目级初始化执行 `openspec init`。任务初始化调用当前 OpenSpec CLI 支持的 `openspec new change <change-id>`，随后提示 Agent 使用已安装工具提供的 OpenSpec propose 工作流生成 proposal/spec/design/tasks。propose 是 AI 工具工作流，不作为 `openspec` CLI 子命令执行。

## 三阶段迭代

1. `gait task init --name "功能名" --type feature` 创建任务并选中 normal-iteration；阶段一先逐项澄清未明确需求，一次只问一个问题；用户明确确认需求理解前，不创建需求设计文档或 OpenSpec artifacts，确认后再写文档和 artifacts，禁止改业务代码。
2. `gait task gate` 查看阶段门禁；门禁通过后 `gait task advance` 交互确认，或在非交互环境显式传 `--yes`。阶段二按 tasks.md 逐项实现、测试、登记 task_id，并编写 coding manifest。
3. 阶段二门禁通过后再次 advance 进入 closing；编写 summary 并运行 `gait task close`，由 CLI 执行 OpenSpec archive、验证 close gate 并置 completed。

`gait task status` 汇报阶段与缺失产物，`gait task rollback --reason "原因"` 回退并将当前阶段已有产物存入 `.gait/trash/`。人工审批只能由用户显式运行 `gait task gate --approve --approver "姓名" --comment "说明"`；Agent 不可自行 approve。

## 状态安全

`.gait/tasks/<task-id>/state.yaml` 是任务唯一真相源；`.gait/project.yaml` 和 `.gait/tasks-index.yaml` 也由 Gait 管理。所有状态变更只允许通过 `gait` CLI，禁止被约束的 Agent、用户脚本或业务代码直接编辑这些 YAML。推进和审批均带时间与操作者审计记录，新会话可从 state 恢复。

Engine 变更后运行：`python gait-engine/scripts/validate_engine.py`。有关 workflow/stage/gate/context/selector 语义见 `gait-engine/docs/ENGINE.md`。
