## Why

产品智能体名称由「小A」更名为「智多星」，需全仓库统一替换（代码字符串、提示词、UI、文档、脚本文件名、规格文本），避免新旧名称混用造成品牌与文档不一致。

## What Changes

- 全量替换「小A」→「智多星」（含「Hello，小A」→「Hello，智多星」），覆盖 33 个文件约 90 处（代码、prompts、静态页、文档、openspec 规格与变更、脚本、面试资产）。
- 文件名改名：`启动小A.bat` / `启动小A.command` → `启动智多星.bat` / `启动智多星.command`，同步更新引用。
- 代码中的日志/审计/响应文案同步更新；运行时日志文件（logs/）为生成物，不回溯改写。
- CHANGELOG 记录更名事项。

## Capabilities

### New Capabilities

### Modified Capabilities

无规格级行为变更（纯命名替换），`.openspec.yaml` 已设 `skip_specs: true`；规格正文中的产品名作为文本随本 change 直接更新。

## Impact

- 代码：`enterprise-agent/app/`（main.py、prompts/defaults.py、graph/aggregator.py、static/index.html、__init__.py）、`docker-compose.prod.yml`、`Dockerfile.prod`、`deploy/`、`pyproject.toml`、`requirements.txt`、`.env.example`
- 文档：根目录 README/AGENTS/CHANGELOG/contents、docs/ 多册、openspec/ 规格与变更、interview/ 资产
- 脚本：`启动小A.bat`、`启动小A.command`（改名）
