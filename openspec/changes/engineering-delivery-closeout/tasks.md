## 0. S0：交付计划与边界（本轮授权）

- [x] 0.1 建立 proposal、design、engineering-delivery delta 与本任务清单。
- [x] 0.2 落盘工程基线；ISSUES 登记 C01–C25；ROADMAP 登记 S0–S7；DECISIONS 追加边界决策。
- [x] 0.3 更新索引、OpenSpec context 与阶段总结，检查链接/锚点、覆盖关系和只改文档的范围。
- [x] 0.4 记录验证限制，完成本地文档交付后暂停，等待用户确认 S1 首项；不启动运行时代码工作。

S0 验证：83 个本轮链接/锚点、25 个 C 项映射、8 个阶段、8 条需求结构通过；仅文档与 OpenSpec context 改动。OpenSpec CLI 严格校验 BLOCKED，不计为通过；完整记录见 `docs/40-process/阶段性总结_S0工程交付基线.md`（仓库相对路径）。

## 1. S1：可复现环境（1.1 完成；1.2 配置独立交付、运行验收阻塞；1.3 外部模型方案已确认，离线增量完成、真实 API/Linux 验收阻塞）

- [x] 1.1 C24 前置部分：安全验证入口与证据模板；本项只完成前置，C24 最终状态仍 open。<!-- evidence: enterprise-agent/scripts/safe_validate.py; docs/40-process/阶段性总结_C24安全验证前置.md; 12 stdlib regression tests PASS; offline execution PASS, UAT/release BLOCKED -->
- [ ] 1.2 C01 部署产物与入口一致。<!-- configuration implemented; target-runtime acceptance BLOCKED; do not close based on static checks -->
  - [x] 1.2.1 冻结 deployment-artifacts delta，统一镜像/入口配置，补契约检查和部署说明；离线 8 项通过，PyYAML 测试 1 项跳过，另用系统 Ruby 标准库完成真实 YAML 解析与模型契约检查。
  - [ ] 1.2.2 在隔离 Linux 环境完成 Compose 渲染、Nginx 校验、候选镜像身份、UI/登录/SSE/健康/就绪/指标边界验收并记录证据。<!-- BLOCKED: no Docker/Nginx here; model/bootstrap dependencies remain C02/C03; see docs/40-process/阶段性总结_C01部署产物与入口.md -->
- [ ] 1.3 C02 模型与依赖 profile 匹配。
  - [x] 1.3.1 Implement the approved Beijing Bailian / DeepSeek profile, remote adapters, slim build, configuration/startup gates, documentation and offline regressions. 27 offline model/transport tests PASS; real API and Linux acceptance remain BLOCKED.
  - [x] 1.3.2 用户已批准 libpq5；补齐 runner 安装、失败即停止及最终非 root runtime 导入探针，2 项新增静态回归 PASS。实际镜像构建/导入仍由 1.3.3 验收。
  - [ ] 1.3.3 隔离候选真实构建/扫描、模型推理与 LLM 问答、资源测量及缺失配置负例验收。<!-- BLOCKED; see docs/40-process/阶段性总结_C02模型依赖.md -->
- [ ] 1.4 C03 数据库迁移与初始化。

## 2. S2：权限与敏感信息（待逐项授权）

- [ ] 2.1 C04 会话归属校验。
- [ ] 2.2 C05 认证失败闭合与运行时授权。
- [ ] 2.3 C06 凭证、脱敏与 HTML 失败安全。
- [ ] 2.4 C07 检索权限与表达式编码。

## 3. S3：会话与运行状态（待逐项授权）

- [ ] 3.1 C08 请求上下文、历史和依赖语义。
- [ ] 3.2 C09 跨进程状态或明确支持限制。
- [ ] 3.3 C10 checkpoint 持久化和故障语义。

## 4. S4：执行一致性与恢复（待逐项授权）

- [ ] 4.1 C18 前置部分：冻结参考系统幂等、失败和补偿契约，C18 完整验收留 S5。
- [ ] 4.2 C12 工具幂等与安全重试。
- [ ] 4.3 C14 队列可靠性与 worker 初始化。
- [ ] 4.4 C13 Saga 持久化与故障恢复。
- [ ] 4.5 C11 审批原子领取、过期与执行状态。

## 5. S5：数据与参考集成（待逐项授权）

- [ ] 5.1 C15 知识发布与索引一致性。
- [ ] 5.2 C16 分析数据适配。
- [ ] 5.3 C17 RAG 质量与指标口径。
- [ ] 5.4 C18 完整参考 HTTP 集成。
- [ ] 5.5 C19 受控 IdP 的 SSO 完整链路。

## 6. S6：用户操作与运维（待逐项授权）

- [ ] 6.1 C20 浏览器角色流程与前端交付。
- [ ] 6.2 C21 就绪、审计、指标和告警。
- [ ] 6.3 C22 备份恢复与回退。
- [ ] 6.4 C23 规定负载下的性能与容量。

## 7. S7：最终候选收口（待逐项授权）

- [ ] 7.1 C24 最终候选自动化、参考环境与人工验收回归。
- [ ] 7.2 C25 Git/文档/版本/支持边界一致性检查与交付结论。
- [ ] 7.3 运行 OpenSpec 严格校验，完成 delta 同步及归档前检查；仅在所有工程验收满足且用户确认后归档，真实企业两个 change 继续独立管理。

逐项验收唯一入口：[ISSUES C01–C25](../../../docs/40-process/ISSUES.md#engineering-closeout)。
阶段顺序唯一入口：[ROADMAP S0–S7](../../../docs/40-process/ROADMAP.md#engineering-closeout-stages)。
S0 完成不代表上述 25 项完成；不将 CLI 未执行记录为严格校验成功。
