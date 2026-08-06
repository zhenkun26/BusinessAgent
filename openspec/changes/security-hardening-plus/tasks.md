## 1. 密钥管理规程与选型落档

- [x] 1.1 盘点全部密钥与凭证（JWT 密钥、PG 口令、Redis 密码、DeepSeek API Key、GHCR token），形成密钥清单
- [x] 1.2 为每类密钥编写轮换周期、轮换步骤与验证方式，补入 `docs/30-guides/运维维护手册.md`
- [x] 1.3 编写密钥泄漏应急处置流程（吊销、轮换、影响面核查、审计记录）并入运维手册
- [x] 1.4 密钥管理工具选型结论（环境变量 + 规程 + 扫描，Vault 暂缓及改判条件）按既有格式追加到 `docs/40-process/DECISIONS.md`

## 2. 密钥防泄漏扫描

- [x] 2.1 配置 pre-commit 密钥扫描钩子（gitleaks 或 detect-secrets），含文档示例串的 allowlist
- [x] 2.2 CI 增加密钥扫描兜底 step，命中疑似密钥时检查失败
- [x] 2.3 核对 `.gitignore` 对 `.env` 及同类密钥文件的覆盖，用含假密钥的提交验证拦截生效

## 3. CI 依赖与镜像漏洞扫描

- [x] 3.1 test job 增加 pip-audit 扫描 `deploy/requirements-prod.txt`，High/Critical 阻断、Medium 及以下告警
- [x] 3.2 docker job 增加 Trivy 镜像扫描 step，High/Critical 时 `exit-code` 失败，报告随 artifact 留存
- [ ] 3.3 建立豁免清单机制（配置文件 + 复评日期），推送验证 CI 全绿

## 4. 权限与越权测试用例

- [x] 4.1 新增 `tests/test_privilege_escalation.py`：跨部门命名空间取数被拒绝/过滤（断言 `can_access_namespace` 与降级链口径）
- [x] 4.2 禁用用户持旧 JWT 访问受保护接口返回 401（`auth_check_db=True`），补降级模式「告警但放行」的显式断言
- [x] 4.3 角色降级（经理→销售）后旧 token 按 DB 新角色判定权限
- [x] 4.4 越权使用他角色工具被 ToolGateway 拒绝；全部用例纳入 CI 回归，58 用例基线之上全绿

## 5. I-06 checkpoint 滑动过期

- [x] 5.1 checkpointer Redis 写入路径增加 thread 键 TTL 刷新，TTL 值走配置项（初值 7 天）
- [x] 5.2 补单元测试断言过期设置生效，跑 `eval/run_w6_checkpoint` 回归

## 6. I-07 token usage 统一采集

- [x] 6.1 实现 LangChain callback 统一采集 token，挂接到统一 chat model 封装，覆盖 analysis/execution/aggregator/knowledge 全部调用方
- [x] 6.2 汇总落三处：审计 payload、Prometheus counter（`app/observability/metrics.py`）、异步回写 `sessions.token_count`（失败仅记日志）
- [x] 6.3 移除 knowledge 原有 `tokens_used` 独立提取口径，补单元测试并跑 W5 对话回归

## 7. 收口与归档

- [x] 7.1 更新 `docs/40-process/ISSUES.md`：I-06/I-07 状态改 fixed 并写明修复与验证
- [ ] 7.2 全量测试套件 + CI 三 job 全绿，运行 `openspec validate security-hardening-plus --strict` 通过后归档
