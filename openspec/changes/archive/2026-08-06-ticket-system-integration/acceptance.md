# 工单真实接入联调验收（ticket-system-integration）

> 任务 5.1（环境依赖清单）与 6.2（验收记录）的书面产出。
> 联调实例类型：**临时 stub**（`enterprise-agent/eval/ticket_stub_server.py`，
> 非真实工单系统）。真实系统采购到位后须按本用例集重跑全量验收。

## 环境依赖清单（5.1）

联调实例：本地临时 stub（Python/FastAPI，复用项目既有依赖，无新增第三方包）。

| 依赖项 | 配置方式 | 说明 |
|---|---|---|
| 工单系统 base URL | 环境变量 `TICKET_API_BASE=http://127.0.0.1:9810/api/v1` | 映射 `app/config.py` 的 `ticket_api_base`；工具层在其后拼 `/tickets` |
| 凭证注入 | 环境变量 `TICKET_API_TOKEN`（pydantic-settings 读取，仅环境变量/`.env`，不落代码） | stub 侧期望 token 由 `TICKET_STUB_TOKEN` 设置，二者一致即可通过认证；错误凭证返回 401 |
| 提供方开关 | 环境变量 `TOOL_PROVIDER=http` | mock 为降级回退通道，验收用例 6 覆盖切换 |
| 重试/超时 | `EXTERNAL_MAX_RETRIES=2`、`EXTERNAL_TIMEOUT_SECONDS=3`（验收值） | 对应 `external_max_retries`/`external_timeout_seconds` |
| stub 启动 | `cd enterprise-agent && .venv/bin/python -m eval.ticket_stub_server`（独立运行，端口 9810）；验收脚本 `run_ticket_acceptance.py` 会自启同进程 stub，无需手工启动 | 内存态，进程重启即丢，符合临时 stub 定位 |
| 网络连通性检查 | `curl http://127.0.0.1:9810/health`（免认证，返回 `{"status":"ok"}`）；认证检查 `curl -H "Authorization: Bearer $TICKET_API_TOKEN" http://127.0.0.1:9810/api/v1/tickets` | 验收 harness 启动时先轮询 `/health` 确认可达，再执行用例 |

环境约束：本机 Docker 守护进程不可用，PostgreSQL/Redis/Milvus 全栈 E2E 跑不了；
验收以「stub + 工具层/调用层 harness」为准，worker 退避重试与审计 DB 回写路径
由单元测试覆盖（`tests/test_ticket_external.py`）。

执行命令（可重复执行，脚本启动时先 reset stub 状态）：

```bash
cd enterprise-agent && .venv/bin/python -m eval.run_ticket_acceptance
# 全部通过退出码 0，任一用例失败退出码 1
```

## 验收记录（6.2）

- 日期：2026-08-06
- 实例类型：**临时 stub**（非真实工单系统实例）
- 执行：`python -m eval.run_ticket_acceptance`，退出码 0，**7/7 全部通过**

| 用例 | 对应规格 Scenario | 结果 | 关键断言 |
|---|---|---|---|
| 0 connectivity | 联调环境依赖明确 | ✓ PASS | `/health` 可达；认证列表端点可用 |
| 1 normal_create_update | 正常创建/更新 | ✓ PASS | 创建工单真实落 stub（TK-STUB0001）；PATCH 更新 status=resolved |
| 2 idempotent_retry | 重试不产生重复工单 | ✓ PASS | 注入「建单后响应丢失」503，重试携带相同 `Idempotency-Key`（`ticket-acc-idem-001-f1b16127`），stub 去重命中 1 次，至多 1 张工单 |
| 3 4xx_no_retry | 4xx 不重试 | ✓ PASS | 错误凭证 → 401 立即失败，stub 侧 POST 计数=1（零重试），错误信息不含凭证 |
| 4 5xx_retry_exhausted | 5xx 触发退避重试 | ✓ PASS | 持续 503 → 退避重试 2 次后耗尽（POST 计数=3=首次+2 重试），返回 `success=false` 结构化结果，`side_effects.external_attempts=3` |
| 5 saga_compensation | 创建补偿关闭外部工单 / 更新补偿恢复旧值 / 调用结果完整入审计 | ✓ PASS | 创建补偿 PATCH 关闭并标注 `closure_reason=saga_compensation`；更新补偿 PATCH 恢复 `old_values`（status=open/priority=high）；补偿动作（close/restore）、幂等键、重试次数完整入审计 |
| 6 mock_fallback | 切换回 mock 不发网络请求 / 真实系统故障时降级可用 | ✓ PASS | `tool_provider=mock` 全流程 stub 计数零增长，Mock 数据契约正常 |

### 覆盖边界（如实声明）

- **worker 退避重试**（补偿失败 → saga_retry 队列 → 退避重排 → 置 compensated/failed）
  与**审计 DB 回写**（本地缓存 → `flush_local_cache` → INSERT + 删除缓存文件）路径
  由单元测试覆盖（`tests/test_ticket_external.py` 共 12 项，含 FakeSession 断言），
  本验收脚本不依赖 PostgreSQL/Redis。沙箱无 PG，验收期间审计实际走本地缓存路径，
  用例 5 的审计断言即在该路径上完成（顺带验证了「数据库不可用时审计不丢」语义）。
- **`UpdateTicketTool._call_external` 的 `old_values` 为空占位**（设计留白，见
  design.md Open Questions）：http 提供方执行更新时不采集旧值，更新补偿用例以直接
  构造 `compensation_data` 的方式验证补偿通道本身。真实系统到位后需确认其 PATCH
  响应是否回传旧值，或补充「更新前 GET 当前值」逻辑后再端到端验证恢复链路。
- 验收期间发现并修复一个审计缺陷：`AuditLogger._write_local_cache` 文件名精度为秒，
  同秒同 event_type 的多条记录互相覆盖（补偿 close/restore 同秒发生时丢一条）。
  已修复为纳秒时间戳文件名（`app/observability/audit.py`），修复后验收 7/7 通过。

### 后续（真实系统到位时）

1. 将 `TICKET_API_BASE`/`TICKET_API_TOKEN` 指向真实实例，重跑本用例集。
2. 优先验证真实系统对 `Idempotency-Key` 的支持；若不支持，按 design Risks 降级为
   「重试前查询是否已建单」，结论追加到 `docs/40-process/DECISIONS.md`。
3. 核对真实系统字段命名/错误码体系与 stub 契约的偏差，必要时调整 `_call_external`。
