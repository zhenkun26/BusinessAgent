## Why

CRM 与邮件工具虽已具备双通道契约（`_call_external` + `http_adapter` + `tool_provider` 开关），但默认 `tool_provider=mock`，真实 HTTP 路径从未对真实系统验证过：CRM 仍只服务 8 客户 8 订单的内存数据（`app/tools/crm.py`），邮件只写入内存字典（`app/tools/mail.py`），员工登录也只有本地密码一条路径（`app/api/auth.py`）。`ticket-system-integration` 已用工单验证了「契约确认 → 真实接入 → 灰度切流」的接入模式，本 change 按同一模式跟进 CRM、邮件两个业务系统，并接入企业 IdP 的 SSO 登录，让系统身份与核心业务数据真正来自企业真实系统。

## What Changes

- **CRM 真实接入**：`query_customer` / `query_order` / `create_crm_task` 三个工具对接真实 CRM API；`create_crm_task` 引入幂等键防重复建单，补偿（删除任务）走真实 API；Mock 保留为降级回退。
- **邮件真实接入**：`send_email_internal` / `send_email_external` 对接真实邮件 API；外部发送维持 `requires_approval=True` 的审批前置；补偿（撤回）按真实能力降级为「撤回请求 + 审计事件」；Mock 保留为降级回退。
- **SSO 登录接入**：新增企业 IdP（OIDC）登录路径，与本地密码登录并存；首次 SSO 登录按 IdP 返回的用户信息自动开通/映射本地账号；IdP 不可用时回退本地密码登录。
- **降级与灰度**：三个系统均按环境变量开关切换真实/Mock，逐系统灰度；真实接入的凭证仍只来自环境变量。

## Capabilities

### New Capabilities

<!-- 无新增能力：CRM/邮件接入复用 external-system-integration 规格，SSO 复用 user-lifecycle 规格。 -->

### Modified Capabilities

- `external-system-integration`: 新增 CRM 与邮件工具真实 HTTP 接入的需求（契约一致性、幂等建单、补偿降级、Mock 回退），工单模式验证后的推广。
- `user-lifecycle`: 新增 SSO 登录需求——企业 IdP 认证路径、首次登录账号开通/映射、IdP 故障时回退本地密码登录。

## Impact

- 代码：`app/tools/crm.py`、`app/tools/mail.py`（真实路径完善与幂等）、`app/api/auth.py`（SSO 登录端点）、`app/security/`（IdP 令牌校验）、`app/config.py`（IdP 与开关配置）、`app/static/index.html`（SSO 登录入口）。
- 配置：新增 IdP issuer/client_id/client_secret、CRM/邮件真实 base URL 与凭证等环境变量（`.env.example` 同步）。
- 依赖：`ticket-system-integration` 验证过的接入模式与验收口径；复用已有 `httpx`，可能新增 OIDC 令牌验签库（design 中定夺）。
- 外部系统：企业 CRM、邮件系统、IdP 三方需提供测试环境与接口契约确认。
- 规格：`external-system-integration` 与 `user-lifecycle` 各追加 ADDED Requirements（归档后发布）。
