## Context

`enterprise-agent/Dockerfile.prod` 使用多阶段构建：builder 生成 `/opt/venv`，runner
随后复制该目录。当前 runner 的 pip 清理命令位于 venv `COPY` 之前，且同一条 `RUN`
中第二个命令直接调用尚不存在的 `/opt/venv/bin/pip`，导致 CI 在镜像构建阶段退出。

## Goals / Non-Goals

**Goals:**

- 让 runner 阶段先获得 builder 产出的 venv，再清理 venv 内的 pip。
- 同时清理基础镜像系统 Python 的 pip，保持运行时镜像不提供 pip 的安全目标。
- 保持应用依赖、启动命令、非 root 用户和镜像分层策略不变。

**Non-Goals:**

- 不调整依赖版本、Trivy 豁免或生产运行时配置。
- 不把 pip 清理逻辑扩展到 builder 阶段；builder 仍需要 pip 安装依赖。

## Decisions

### 1. 将 venv COPY 放到 runner pip 清理之前

runner 先执行基础镜像 pip 清理，再复制 `/opt/venv`，最后用 venv 自己的 Python
执行 pip 清理。这样每个命令只访问已经存在的路径，避免依赖 PATH 的隐式解析。

备选：只删除 `/opt/venv/bin/pip` 文件。否决：无法清理 pip 的 site-packages/vendor
内容，不能解决触发 Trivy 的漏洞来源。

### 2. 使用显式 Python 路径执行两次清理

基础镜像清理使用 `/usr/local/bin/python`，venv 清理使用 `/opt/venv/bin/python`。
这样不会因 `PATH` 顺序或 venv 是否已复制而调用错误的 Python 环境。

## Risks / Trade-offs

- [Risk] pip 卸载可能移除对应的 pip 启动脚本 → [Mitigation] 只在 runner 阶段执行，应用运行依赖的是已安装包和 venv Python，不依赖 pip。
- [Risk] Docker 层顺序变化导致缓存失效 → [Mitigation] 仅调整 runner 的安全清理层，builder 依赖层保持不变。
