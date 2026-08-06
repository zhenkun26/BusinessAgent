## Context

动机见 proposal.md 的 Why。技术现状：CRM（`app/tools/crm.py`）与邮件（`app/tools/mail.py`）的 `_call_external` 已按真实 API 契约写好（GET `/customers/{id}`、GET `/orders/{id}`、POST `/crm_tasks`、POST `/send`），统一走 `app/tools/http_adapter.py`（超时/指数退避/401 不重试/凭证不入日志），由 `config.tool_provider`（默认 `mock`）全局切换，`BaseTool` 支持单工具 `provider_override`。登录路径只有本地密码一条：`app/api/auth.py` 的 `POST /api/v1/auth/login` 校验 `verify_password` 后由 `app/security/jwt_manager.py` 签发 JWT；登录接口有限流 10 次/分钟（`app/middleware/rate_limit.py`）。`ticket-system-integration` 已验证「契约确认 → 契约测试 → 灰度切流」模式，本 change 直接复用其结论与验收口径。

## Goals / Non-Goals

**Goals:**
- CRM 三工具与邮件双工具在真实提供方下行为与 Mock 契约一致，写操作幂等、补偿真实生效。
- SSO 登录（OIDC 授权码流程）与本地密码登录并存，首次登录账号映射/开通可审计。
- 三个系统均可独立开关、可回退 Mock/本地登录，灰度过程不破坏现有会话与工具契约。

**Non-Goals:**
- 不改造 `http_adapter` 与 `tool_provider` 机制本身（已在位且经工单验证）。
- 不做 CRM/邮件数据的反向同步（如把 CRM 全量客户导入本地库），只按工具调用实时查询。
- 不做 IdP 侧的组织/角色同步与 SCIM 开通，首次登录仅按默认角色开通。
- 不实现邮件发送的本地队列化（发送失败按既有结构化失败返回，重试由 Saga/审批流承载）。

## Decisions

### 1. 幂等键在工具层生成，键 = Saga 执行 ID + 工具调用序号

`create_crm_task` 的幂等键由工具层在首次调用时生成并随 `compensation_data`/Saga 上下文持久化，格式 `{saga_execution_id}:{tool_call_index}`；重试与审批后重放复用同一键。CRM 侧需支持幂等键（请求头 `Idempotency-Key`），契约确认时核实；若 CRM 不支持，退化为「先按客户+标题查重再创建」的两步方案并在 DECISIONS 记录。

备选：由 http_adapter 统一注入幂等键。否决：适配层无法区分「安全重试」与「新的一次业务创建」，键的边界必须在工具层划定。

### 2. 邮件补偿对外部发送明确降级，不假装可撤回

真实邮件系统通常无法真正撤回已送达邮件。补偿动作统一调用邮件系统的撤回接口（内部邮件可成功、外部邮件仅为请求），补偿结果如实标注；外部邮件的风险控制前置到审批与 RBAC（维持 `requires_approval=True`、仅 manager/admin），不依赖补偿兜底。

备选：所有外发邮件先落本地队列、延迟可撤回窗口后再真实发送。否决：改变发送语义且引入新组件，超出本 change 范围；记入 Open Questions 供后续评估。

### 3. SSO 采用 OIDC 授权码流程，账号映射键 = IdP `sub` + issuer

新增 `GET /api/v1/auth/sso/login`（重定向 IdP）与 `GET /api/v1/auth/sso/callback`（换码验签）两个端点；验签校验签名（JWKS）、iss、aud、exp，通过后按 `(issuer, sub)` 在 `users` 表新增的唯一映射列（或映射表）查找本地用户，未命中则按默认角色（salesperson）与 IdP 返回的部门声明自动开通，随后复用既有 `jwt_manager` 签发本系统 JWT——下游鉴权零改动。验签库选型在实施时按现有依赖定夺（优先复用已用的 `PyJWT` + JWKS 端点拉取公钥，避免引入新重依赖）。

备选：SAML。否决：企业 IdP 普遍支持 OIDC，且授权码流程与现有 JWT 体系衔接最简；SAML 解析引入 XML 安全面，得不偿失。
备选：用 IdP 令牌直接作为会话令牌。否决：令牌生命周期与吊销不受本系统控制，且无法承载本地角色声明。

### 4. 降级策略分系统定调：查询回退 Mock 仅用于演练，登录回退本地密码

CRM/邮件真实提供方故障时，工具层按既有契约返回结构化失败（不自动改道 Mock——真实模式下返回 Mock 数据会污染业务判断）；Mock 回退只通过显式开关切换，用于演练与契约验证期。SSO 的降级则是功能性的：IdP 不可用时本地密码登录始终可用，SSO 入口返回明确提示。

备选：真实调用失败自动回退 Mock。否决：静默返回 8 客户 Mock 数据会被当成真实查询结果，违反「真实模式不说谎」原则。

## Risks / Trade-offs

- CRM 不支持幂等键 → 契约确认任务前置核实，退化为查重式两步创建并记录决策；仍不满足则 create 保持 Mock 仅查询走真实。
- 外部邮件撤回实际无效 → 规格与补偿文案均如实标注，风险控制靠审批前置；在使用手册中向用户说明。
- SSO 自动开通可能放大 IdP 侧账号管理失误（IdP 误建账号即在本系统开通）→ 默认角色给最低权限 salesperson，开通即审计，管理员可禁用。
- 三系统契约确认依赖外部团队排期 → tasks 将契约确认列为第一里程碑，未确认前不进入联调。
- `users` 表增加 SSO 映射列属于 schema 变更 → 走既有迁移方式，回滚仅删列，不影响既有密码登录。

## Migration Plan

1. 契约确认：与 CRM/邮件/IdP 三方确认接口契约（含幂等键、撤回语义、OIDC 端点与声明）。
2. 实现与契约测试：开发真实路径 + SSO 端点，以 Mock 服务器做契约测试，单元测试覆盖失败与降级路径。
3. 测试环境联调：`tool_provider` 按系统逐一切真实，跑通 `eval/` 相关验证。
4. 灰度切流：先 CRM 查询类 → CRM 创建 → 内部邮件 → 外部邮件 → SSO，每步观察日志与审计。
5. 回滚：任一环节异常即把对应系统开关切回 Mock/隐藏 SSO 入口，回滚动作留审计记录。

## Open Questions

- IdP 的具体提供方（ADFS / Keycloak / 企业微信等）与部门声明字段名，契约确认时落实。
- 外发邮件是否需要「延迟可撤回窗口」的发送队列？本 change 不做，灰度后按误发率评估是否单开 change。
- SSO 开通用户的部门声明缺失时的归属策略（默认部门还是拒绝开通并转人工），评审时定。
