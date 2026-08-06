## Why

项目已有 58 用例回归套件与 v1.0.0 的 12 项安全漏洞修复基线（ISSUES I-11），但按「真实企业上线」评审（`docs/40-process/优化方向分析-生产上线-2026-08-05.md` 阶段三），安全面仍有三个硬缺口：密钥仅靠环境变量管理、无轮换规程与防泄漏扫描；CI（`.github/workflows/ci.yml`）只跑测试与镜像构建，无依赖/镜像漏洞扫描；权限测试只有正向用例，缺横向越权（跨部门取数、禁用用户持旧 JWT）的对抗性用例。另有两个已知实现债务需顺带收口：ISSUES I-06（checkpoint 无 TTL）与 I-07（token usage 部分采集未接入）。

## What Changes

- **密钥管理方案**：盘点全部密钥/凭证（JWT 密钥、数据库口令、Redis 密码、外部 API Key），制定密钥轮换规程与泄漏应急处置流程，并对「是否引入密钥管理工具（如 Vault）」给出选型结论；同时建立防泄漏机制（pre-commit/CI 的密钥扫描 + `.env` 管控核对）。
- **CI 漏洞扫描**：在 `.github/workflows/ci.yml` 接入 Python 依赖漏洞扫描（pip-audit 或同类）与容器镜像漏洞扫描（Trivy 或同类），定义阻断门槛（如 High/Critical 阻断合并）。
- **权限与越权测试用例**：补齐对抗性测试——横向越权访问他部门命名空间数据、越权使用他角色工具、禁用用户持旧 JWT 访问（`auth_check_db` 开启与降级两种模式）、角色变更后旧 token 的权限即时性。
- **I-06/I-07 收口**（实现任务，落入 tasks）：checkpoint 按会话最近活跃时间滑动过期；token usage 经 LangChain callback 统一采集，落审计 payload + Prometheus counter 并回写 `sessions.token_count`。

## Capabilities

### New Capabilities
- `security-operations`: 密钥全生命周期管理（轮换规程、泄漏应急、选型结论与防泄漏扫描）、CI 依赖与镜像漏洞扫描及其阻断门槛、权限与越权对抗性测试的必备用例集与通过标准。

### Modified Capabilities

<!-- 越权测试与扫描门槛作为新能力 security-operations 的需求承载；
     user-lifecycle / quality-testing 的既有需求不做规格级修改。 -->

## Impact

- 代码：`enterprise-agent/app/graph/checkpointer.py`（I-06 TTL）、`enterprise-agent/app/observability/`（I-07 token 采集）、`enterprise-agent/tests/` 新增越权测试文件。
- CI：`.github/workflows/ci.yml` 新增依赖扫描与镜像扫描 job。
- 文档：`docs/30-guides/运维维护手册.md` 补密钥轮换规程与泄漏应急章节；`docs/40-process/ISSUES.md` 更新 I-06/I-07 状态；选型结论落 `docs/40-process/DECISIONS.md`。
- 依赖：新增扫描工具依赖（pip-audit/Trivy，仅 CI 环境）；I-07 需确认 LangChain callback 与现链路兼容。
- 上游依赖：本 change 的验收安全门槛将被 `uat-and-ga-rollout` 引用。
