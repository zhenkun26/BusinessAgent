## 1. 幂等与重试实现

- [x] 1.1 在 `app/tools/ticket.py` 的 `CreateTicketTool._call_external` 中生成幂等键（复用 `context["request_id"]`），经 `call_external_api` 的 `extra_headers` 以 `Idempotency-Key` 头传递，并写入 `side_effects` 供审计关联
- [x] 1.2 核对 `http_adapter.py` 重试边界与规格一致（5xx/网络错误退避重试、4xx 立即失败、耗尽返回 `success=false`、日志不含凭证），不一致处修正

## 2. Saga 补偿真实化

- [x] 2.1 改造 `CreateTicketTool.compensate`：http 提供方下调用外部系统关闭工单并标注 `saga_compensation`，mock 提供方行为保持不变
- [x] 2.2 改造 `UpdateTicketTool.compensate`：http 提供方下调用外部系统恢复 `old_values`，mock 提供方行为保持不变
- [x] 2.3 验证补偿失败时由 worker 按退避策略重试并记录最终结果（复用既有 worker 机制，补齐工单场景断言）

## 3. 审计回写验证

- [x] 3.1 确认真实调用结果（成功/失败/重试次数/补偿动作/幂等键）完整写入审计日志，缺失字段补齐
- [x] 3.2 验证数据库不可用时审计写入本地缓存、恢复后由 worker 回写并标记已同步（工单场景覆盖）

## 4. 单元测试

- [x] 4.1 新增幂等键测试：同键重复调用不产生重复请求体差异、键随 `request_id` 稳定
- [x] 4.2 新增补偿真实化测试：Mock http 层断言补偿调用外部系统（关闭/恢复旧值）及失败重试路径
- [x] 4.3 回归既有工单 Mock 通道测试与 `tool_provider=mock` 行为，确保 Mock 通道零变更
- [x] 4.4 运行 `pytest tests/` 全绿

## 5. 联调环境准备

- [x] 5.1 确认联调工单系统选型（真实实例或临时 stub），产出书面的联调环境依赖清单（base URL、凭证注入方式、网络连通性检查）
- [x] 5.2 配置联调环境：`ticket_api_base` 指向联调实例、`ticket_api_token` 经环境变量注入、容器内连通性验证通过

## 6. 联调验收

- [x] 6.1 执行验收用例集：正常创建/更新、幂等重试（同键重复提交至多一张工单）、4xx/5xx 错误路径、Saga 补偿与 worker 重试、审计回写、mock 降级切换
- [x] 6.2 记录验收结果（标注 stub/真实实例），全部用例通过后归档；选型与幂等键能力结论按需追加到 `docs/40-process/DECISIONS.md`
- [x] 6.3 运行 `openspec validate ticket-system-integration --strict` 通过后归档
