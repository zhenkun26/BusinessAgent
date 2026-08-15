## Why

最近一次 CI 的单元测试全部通过，但生产镜像在 runner 阶段构建失败。Dockerfile 在复制
builder 生成的虚拟环境之前调用 `/opt/venv/bin/pip`，导致命令不存在并阻断镜像发布。

## What Changes

- 调整 runner 阶段的 venv 复制与 pip 清理顺序，保证清理动作只访问已存在的路径。
- 保留运行时不携带 pip 的安全目标，避免重新引入 pip 内置 vendor 漏洞。
- 增加等价的 Docker 构建验证，确认生产镜像可构建且 runner 不依赖 pip。

## Capabilities

### New Capabilities

无。本 change 只修复生产镜像构建顺序，不新增用户可见或运行时能力。

### Modified Capabilities

无。根据项目 OpenSpec 规则，本 change 通过 `.openspec.yaml` 的 `skip_specs: true` 标记为纯工程/部署修复。

## Impact

- 影响 `enterprise-agent/Dockerfile.prod` 及 CI 的 Docker build job。
- 不改变 API、业务逻辑、数据库结构或运行时权限模型。
- 修复后需要重新运行 Python 单元测试、Docker 构建和镜像安全扫描。
