## 1. Dockerfile 修复

- [x] 1.1 调整 runner 阶段的 venv 复制与系统/venv pip 清理顺序，改用显式 Python 路径 <!-- evidence: enterprise-agent/Dockerfile.prod -->
- [x] 1.2 增加或更新构建检查，确认生产 Dockerfile 不再在 venv 复制前访问 `/opt/venv/bin/pip` <!-- evidence: enterprise-agent/tests/test_dockerfile_prod.py -->

## 2. 验证与收口

- [x] 2.1 运行 Python 单元测试、静态检查和 Docker 生产镜像构建 <!-- Python/static passed; GitHub Actions run 31890705614 passed on Python 3.11/3.13 and production image build -->
- [x] 2.2 运行 `openspec validate fix-prod-image-pip-removal --strict`，记录 CI 修复证据并准备归档 <!-- strict passed; GitHub Actions run 31890705614 passed including Trivy HIGH/CRITICAL scan -->
