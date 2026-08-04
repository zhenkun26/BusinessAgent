"""工具执行层(W7):对接外部业务系统

模块结构:
- base.py:        ToolGateway 抽象 + ToolResult 数据契约 + 工具注册表
- schemas.py:     各工具入参/出参 Pydantic Schema
- crm.py:         CRM 工具(查询客户/订单/创建 CRM 任务)
- mail.py:        邮件工具(内部/外部邮件发送)
- ticket.py:      工单工具(创建/更新工单)
- security.py:    工具权限校验 + Prompt 注入防护
- saga.py:        Saga 补偿事务协调器(多步骤执行 + 反向回滚)

设计原则:
- 业务系统 API 暂用 Mock 实现(内部系统无法真实对接),但接口契约完整
- 切换真实 API 只需改 ToolGateway 实现的 _call_external 方法
- 所有工具调用走 ToolGateway,统一权限校验 + 日志 + 限流
- Saga 协调器管理多工具调用的补偿事务
"""
