## 1. 外部系统契约确认

- [ ] 1.1 与 CRM 团队确认接口契约：查询/建单字段、幂等键（`Idempotency-Key`）支持与否、删除任务接口；结论写入 design 决策 1 的落点并在 `docs/40-process/DECISIONS.md` 留记录
- [ ] 1.2 与邮件团队确认接口契约：`/send` 字段、内部/外部撤回能力与语义（真实撤回 vs 撤回请求）
- [ ] 1.3 与 IdP 管理员确认 OIDC 端点（authorize/token/JWKS）、client 凭证发放、用户唯一标识与部门声明字段名
- [ ] 1.4 三系统测试环境可用性验证：从开发机可达、凭证有效

## 2. CRM 真实接入

- [ ] 2.1 在 `app/config.py` 增加 CRM/邮件/IdP 相关配置项（base URL、凭证、逐系统 provider 开关），同步 `.env.example`
- [ ] 2.2 完善 `app/tools/crm.py` 真实路径：响应字段归一化为与 Mock 一致的 `ToolResult` 结构；`create_crm_task` 生成并持久化幂等键，补偿走真实删除接口
- [ ] 2.3 为 CRM 三工具补契约测试（Mock HTTP 服务器）：正常路径、401/5xx/超时、幂等重放不重复建单、补偿调用删除接口

## 3. 邮件真实接入

- [ ] 3.1 完善 `app/tools/mail.py` 真实路径：内外发送的 `ToolResult` 结构与 Mock 一致；外部发送维持 `requires_approval=True` 与角色约束
- [ ] 3.2 实现补偿降级：内部邮件真实撤回、外部邮件提交撤回请求并写审计事件，补偿结果如实标注
- [ ] 3.3 为邮件双工具补契约测试：审批前置未被绕过、撤回语义、失败结构化返回且日志无凭证

## 4. SSO 登录接入

- [ ] 4.1 `users` 表增加 SSO 映射（`(issuer, sub)` 唯一约束）的迁移脚本，回滚仅删列
- [ ] 4.2 新增 SSO 端点：`GET /api/v1/auth/sso/login`（重定向 IdP）与 `GET /api/v1/auth/sso/callback`（换码、JWKS 验签、签发本系统 JWT），复用 `jwt_manager`
- [ ] 4.3 实现首次登录账号映射/自动开通（默认 salesperson 角色 + IdP 部门声明），开通与映射写审计日志
- [ ] 4.4 IdP 不可用时 SSO 入口返回明确提示，本地密码登录路径不受影响（回归验证既有登录测试）
- [ ] 4.5 `app/static/index.html` 增加 SSO 登录入口；为 SSO 全流程补单元测试（验签失败、首次开通、已有映射、IdP 故障回退）

## 5. 联调、灰度与归档

- [ ] 5.1 测试环境联调：按系统逐一切真实提供方，运行相关 `eval/` 脚本验证工具链回归
- [ ] 5.2 灰度切流按 design 顺序执行（CRM 查询 → CRM 创建 → 内部邮件 → 外部邮件 → SSO），每步核对日志与审计记录
- [ ] 5.3 更新 `docs/30-guides/运维维护手册.md`（新环境变量、开关与回退操作）与产品使用手册（SSO 登录入口）
- [ ] 5.4 运行 `openspec validate crm-mail-sso-integration --strict` 通过后归档
