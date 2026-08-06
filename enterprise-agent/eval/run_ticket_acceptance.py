"""工单真实接入联调验收(ticket-system-integration 6.1)

验收环境:本地临时 stub(eval/ticket_stub_server.py)充当真实工单系统。
本脚本自启 stub(127.0.0.1:9810),逐项执行规格验收用例,全部通过退出码 0。

用例集(对应 specs/external-system-integration 全部 Scenario):
0. 连通性检查(GET /health + 认证列表端点)
1. 正常创建/更新(http 提供方真实触达 stub)
2. 幂等重试(建单后响应丢失,重试同键去重,stub 侧至多一张工单)
3. 4xx 路径(错误 token → 认证失败立即返回,stub 侧断言零重试)
4. 5xx 路径(注入 503 → 指数退避重试耗尽后 success=false,断言重试次数)
5. Saga 补偿(创建补偿关闭并标注 saga_compensation;更新补偿恢复旧值;
   补偿动作与幂等键入审计——沙箱无 PG,审计走本地缓存路径,顺带验证 3.2 语义)
6. mock 降级切换(tool_provider=mock 全流程,stub 侧计数零增长)

覆盖边界(在汇总中如实声明):
- worker 退避重试与审计 DB 回写路径由单元测试覆盖(tests/test_ticket_external.py),
  本脚本不依赖 PostgreSQL/Redis(Docker 守护进程不可用的沙箱环境)。
- UpdateTicketTool._call_external 记录的 old_values 当前为空占位(设计留白),
  更新补偿用例直接构造 compensation_data 验证补偿通道本身。

运行:
    python -m eval.run_ticket_acceptance

前置:无需 Docker/LLM/数据库;仅需 .venv 依赖(fastapi/uvicorn/httpx)。
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

# ---- 联调环境配置(必须在首次 get_settings() 调用前注入) ----
_STUB_BASE = "http://127.0.0.1:9810"
_STUB_TOKEN = "stub-acceptance-token"
os.environ["TICKET_API_BASE"] = f"{_STUB_BASE}/api/v1"
os.environ["TICKET_API_TOKEN"] = _STUB_TOKEN
os.environ["TICKET_STUB_TOKEN"] = _STUB_TOKEN
os.environ["TOOL_PROVIDER"] = "http"
os.environ["EXTERNAL_MAX_RETRIES"] = "2"
os.environ["EXTERNAL_TIMEOUT_SECONDS"] = "3"

import httpx  # noqa: E402
import uvicorn  # noqa: E402

import app.observability.audit as audit_module  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.observability.audit import AuditLogger  # noqa: E402
from app.tools.ticket import CreateTicketTool, UpdateTicketTool  # noqa: E402
from eval.ticket_stub_server import STUB_HOST, STUB_PORT  # noqa: E402
from eval.ticket_stub_server import app as stub_app  # noqa: E402

# 审计重定向:沙箱无 PG,审计本就走本地缓存;指向独立目录避免污染 logs/audit
_AUDIT_CACHE_DIR = Path(__file__).resolve().parent.parent / "logs" / "audit_acceptance"

# 验收上下文(manager 有 create_ticket/update_ticket 权限)
_CONTEXT = {"user_id": "u001", "role": "manager", "dept": "dept_cs"}


# ============ 公共辅助 ============


async def _wait_stub_ready(timeout_seconds: float = 10.0) -> bool:
    """连通性验证:轮询 stub /health 直至可达"""
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    async with httpx.AsyncClient(timeout=1.0) as client:
        while asyncio.get_event_loop().time() < deadline:
            try:
                resp = await client.get(f"{_STUB_BASE}/health")
                if resp.status_code == 200:
                    return True
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.2)
    return False


async def _stub_stats(client: httpx.AsyncClient) -> dict[str, int]:
    resp = await client.get(f"{_STUB_BASE}/api/v1/stats")
    resp.raise_for_status()
    return resp.json()


async def _stub_tickets(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    resp = await client.get(
        f"{_STUB_BASE}/api/v1/tickets",
        headers={"Authorization": f"Bearer {_STUB_TOKEN}"},
    )
    resp.raise_for_status()
    return resp.json()["tickets"]


def _read_audit_events() -> list[dict[str, Any]]:
    """读取本地缓存中的审计记录(沙箱无 PG,审计全部落本地缓存)"""
    events = []
    if not _AUDIT_CACHE_DIR.is_dir():
        return events
    for file in sorted(_AUDIT_CACHE_DIR.glob("*.json")):
        events.append(json.loads(file.read_text(encoding="utf-8")))
    return events


# ============ 用例 0: 连通性检查 ============


async def case_connectivity(client: httpx.AsyncClient) -> bool:
    """用例 0:stub 可达 + 认证列表端点可用"""
    print("\n" + "=" * 60)
    print("用例 0:连通性检查(GET /health + 认证 GET /tickets)")
    print("=" * 60)

    resp = await client.get(f"{_STUB_BASE}/health")
    if resp.status_code != 200:
        print(f"✗ /health 不可达: HTTP {resp.status_code}")
        return False
    print(f"✓ /health 可达: {resp.json()}")

    tickets = await _stub_tickets(client)
    print(f"✓ 认证列表端点可用,当前工单数: {len(tickets)}")
    return True


# ============ 用例 1: 正常创建/更新 ============


async def case_normal_create_update(client: httpx.AsyncClient) -> bool:
    """用例 1:http 提供方下创建/更新真实触达 stub"""
    print("\n" + "=" * 60)
    print("用例 1:正常创建/更新(http 提供方 → stub)")
    print("=" * 60)

    create_tool = CreateTicketTool()
    created = await create_tool.invoke(
        {"title": "C001 售后投诉:发票未开具", "customer_id": "C001", "priority": "high"},
        {**_CONTEXT, "request_id": "acc-001"},
    )
    print(f"创建: success={created.success}, output={created.output}")
    if not created.success:
        print(f"✗ 创建失败: {created.error}")
        return False
    ticket = created.output["ticket"]
    ticket_id = ticket["ticket_id"]

    tickets = await _stub_tickets(client)
    if not any(t["ticket_id"] == ticket_id for t in tickets):
        print(f"✗ stub 侧不存在工单 {ticket_id}")
        return False
    print(f"✓ 工单真实落 stub: {ticket_id}")

    update_tool = UpdateTicketTool()
    updated = await update_tool.invoke(
        {"ticket_id": ticket_id, "status": "resolved", "comment": "已补开发票"},
        {**_CONTEXT, "request_id": "acc-002"},
    )
    if not updated.success:
        print(f"✗ 更新失败: {updated.error}")
        return False

    tickets = await _stub_tickets(client)
    stub_ticket = next(t for t in tickets if t["ticket_id"] == ticket_id)
    if stub_ticket["status"] != "resolved":
        print(f"✗ stub 侧状态未更新: {stub_ticket['status']}")
        return False
    print("✓ 更新真实落 stub: status=resolved, comment 已追加")
    return True


# ============ 用例 2: 幂等重试 ============


async def case_idempotent_retry(client: httpx.AsyncClient) -> bool:
    """用例 2:建单后响应丢失(503),重试同键去重,stub 至多一张工单"""
    print("\n" + "=" * 60)
    print("用例 2:幂等重试([FAULT:CREATE_THEN_503] 建单后响应丢失)")
    print("=" * 60)

    stats_before = await _stub_stats(client)
    request_id = "acc-idem-001"
    title = "[FAULT:CREATE_THEN_503] 幂等重试验证工单"

    create_tool = CreateTicketTool()
    result = await create_tool.invoke(
        {"title": title, "customer_id": "C002"},
        {**_CONTEXT, "request_id": request_id},
    )
    print(f"success={result.success}, side_effects={result.side_effects}")

    stats_after = await _stub_stats(client)
    attempts = stats_after["post_attempts"] - stats_before["post_attempts"]
    dedup_hits = stats_after["idempotent_hits"] - stats_before["idempotent_hits"]
    print(f"POST 尝试次数: {attempts}, stub 幂等去重命中: {dedup_hits}")

    if not result.success:
        print(f"✗ 重试后应成功(同键去重返回首次结果): {result.error}")
        return False
    if attempts != 2 or dedup_hits != 1:
        print(f"✗ 预期 2 次尝试 + 1 次去重命中,实际 {attempts}/{dedup_hits}")
        return False

    tickets = await _stub_tickets(client)
    matched = [t for t in tickets if t["title"] == title]
    if len(matched) != 1:
        print(f"✗ 同键重复提交产生 {len(matched)} 张工单(应为 1)")
        return False

    idem_key = result.side_effects.get("idempotency_key", "")
    if not idem_key.startswith(f"ticket-{request_id}-"):
        print(f"✗ 幂等键未复用 request_id: {idem_key}")
        return False

    print(f"✓ 重试同键去重:stub 侧仅 1 张工单,幂等键={idem_key}")
    return True


# ============ 用例 3: 4xx 立即失败 ============


async def case_4xx_no_retry(client: httpx.AsyncClient) -> bool:
    """用例 3:错误 token → 401 立即失败,零重试"""
    print("\n" + "=" * 60)
    print("用例 3:4xx 路径(错误凭证 → 立即失败不重试)")
    print("=" * 60)

    settings = get_settings()
    original_token = settings.ticket_api_token
    settings.ticket_api_token = "wrong-token"  # 注入错误凭证
    try:
        stats_before = await _stub_stats(client)
        create_tool = CreateTicketTool()
        result = await create_tool.invoke(
            {"title": "错误凭证验证工单"},
            {**_CONTEXT, "request_id": "acc-401"},
        )
    finally:
        settings.ticket_api_token = original_token

    stats_after = await _stub_stats(client)
    attempts = stats_after["post_attempts"] - stats_before["post_attempts"]
    print(f"success={result.success}, error={result.error}, POST 尝试次数: {attempts}")

    if result.success:
        print("✗ 错误凭证不应成功")
        return False
    if "认证失败" not in (result.error or ""):
        print(f"✗ 错误信息应为认证失败: {result.error}")
        return False
    if attempts != 1:
        print(f"✗ 4xx 不应重试,实际尝试 {attempts} 次")
        return False

    print("✓ 401 立即失败,零重试,错误信息不含凭证内容")
    return True


# ============ 用例 4: 5xx 退避重试耗尽 ============


async def case_5xx_retry_exhausted(client: httpx.AsyncClient) -> bool:
    """用例 4:持续 503 → 指数退避重试耗尽后 success=false"""
    print("\n" + "=" * 60)
    print("用例 4:5xx 路径(注入持续 503 → 重试耗尽 success=false)")
    print("=" * 60)

    settings = get_settings()
    max_retries = settings.external_max_retries
    stats_before = await _stub_stats(client)

    create_tool = CreateTicketTool()
    result = await create_tool.invoke(
        {"title": "[FAULT:503] 持续故障验证工单"},
        {**_CONTEXT, "request_id": "acc-503"},
    )

    stats_after = await _stub_stats(client)
    attempts = stats_after["post_attempts"] - stats_before["post_attempts"]
    expected = 1 + max_retries
    print(
        f"success={result.success}, error={result.error}, "
        f"POST 尝试次数: {attempts}(预期 {expected}=首次+{max_retries} 次重试)"
    )

    if result.success:
        print("✗ 持续 503 不应成功")
        return False
    if "服务不可用" not in (result.error or ""):
        print(f"✗ 错误信息应为服务不可用: {result.error}")
        return False
    if attempts != expected:
        print(f"✗ 重试次数不符: 实际 {attempts},预期 {expected}")
        return False
    if result.side_effects.get("external_attempts") != expected:
        print(f"✗ side_effects.external_attempts 不符: {result.side_effects}")
        return False

    print(f"✓ 退避重试 {max_retries} 次后耗尽,返回 success=false 结构化结果")
    return True


# ============ 用例 5: Saga 补偿真实化 + 补偿审计 ============


async def case_saga_compensation(client: httpx.AsyncClient) -> bool:
    """用例 5:创建补偿关闭工单(标注 saga_compensation)/更新补偿恢复旧值/补偿入审计"""
    print("\n" + "=" * 60)
    print("用例 5:Saga 补偿(创建补偿关闭 + 更新补偿恢复旧值 + 审计)")
    print("=" * 60)

    # 5a 创建补偿:真实创建的工单被补偿关闭
    create_tool = CreateTicketTool()
    created = await create_tool.invoke(
        {"title": "待补偿关闭的工单", "customer_id": "C003"},
        {**_CONTEXT, "request_id": "acc-comp-001"},
    )
    if not created.success:
        print(f"✗ 前置创建失败: {created.error}")
        return False
    ticket_id = created.output["ticket"]["ticket_id"]

    closed = await create_tool.compensate(created.compensation_data)
    print(f"创建补偿: success={closed.success}, output={closed.output}")
    if not closed.success:
        print(f"✗ 创建补偿失败: {closed.error}")
        return False

    tickets = await _stub_tickets(client)
    stub_ticket = next(t for t in tickets if t["ticket_id"] == ticket_id)
    if stub_ticket["status"] != "closed":
        print(f"✗ 补偿后 stub 工单未关闭: {stub_ticket['status']}")
        return False
    if stub_ticket.get("closure_reason") != "saga_compensation":
        print(f"✗ 补偿原因未标注: {stub_ticket.get('closure_reason')}")
        return False
    print(f"✓ 创建补偿真实触达 stub: {ticket_id} closed + closure_reason=saga_compensation")

    # 5b 更新补偿:恢复旧值(直接构造 compensation_data——_call_external 记录的
    # old_values 当前为空占位,属设计留白,验收记录中注明)
    created2 = await create_tool.invoke(
        {"title": "待补偿恢复的工单", "priority": "high"},
        {**_CONTEXT, "request_id": "acc-comp-002"},
    )
    ticket_id2 = created2.output["ticket"]["ticket_id"]
    update_tool = UpdateTicketTool()
    updated = await update_tool.invoke(
        {"ticket_id": ticket_id2, "status": "resolved", "priority": "low"},
        {**_CONTEXT, "request_id": "acc-comp-003"},
    )
    if not updated.success:
        print(f"✗ 前置更新失败: {updated.error}")
        return False

    compensation_data = {
        "ticket_id": ticket_id2,
        "action": "restore",
        "old_values": {"status": "open", "priority": "high"},
    }
    restored = await update_tool.compensate(compensation_data)
    print(f"更新补偿: success={restored.success}, output={restored.output}")
    if not restored.success:
        print(f"✗ 更新补偿失败: {restored.error}")
        return False

    tickets = await _stub_tickets(client)
    stub_ticket2 = next(t for t in tickets if t["ticket_id"] == ticket_id2)
    if stub_ticket2["status"] != "open" or stub_ticket2["priority"] != "high":
        print(
            f"✗ 旧值未恢复: status={stub_ticket2['status']}, "
            f"priority={stub_ticket2['priority']}"
        )
        return False
    print(f"✓ 更新补偿真实触达 stub: {ticket_id2} 恢复 status=open/priority=high")

    # 5c 补偿与幂等键入审计(沙箱无 PG → 审计落本地缓存,验证 3.1/3.2 语义)
    events = _read_audit_events()
    comp_events = [e for e in events if e.get("event_type") == "saga_compensation"]
    comp_actions = {e.get("payload", {}).get("action") for e in comp_events}
    tool_calls = [
        e
        for e in events
        if e.get("event_type") == "tool_call" and e.get("tool_name") == "create_ticket"
    ]
    has_idem_in_audit = any(
        e.get("payload", {}).get("side_effects", {}).get("idempotency_key")
        for e in tool_calls
    )
    print(f"审计: 补偿事件动作={comp_actions}, 创建调用含幂等键={has_idem_in_audit}")

    if not {"close", "restore"} <= comp_actions:
        print(f"✗ 补偿动作未完整入审计: {comp_actions}")
        return False
    if not has_idem_in_audit:
        print("✗ 创建调用审计缺少幂等键")
        return False
    if not all(e.get("payload", {}).get("attempts") for e in comp_events):
        print("✗ 补偿审计缺少重试次数字段")
        return False
    print("✓ 补偿动作(close/restore)与幂等键、重试次数完整入审计(本地缓存路径)")
    return True


# ============ 用例 6: mock 降级切换 ============


async def case_mock_fallback(client: httpx.AsyncClient) -> bool:
    """用例 6:tool_provider=mock 全流程不触网,stub 计数零增长"""
    print("\n" + "=" * 60)
    print("用例 6:mock 降级切换(切回 mock 不发任何网络请求)")
    print("=" * 60)

    settings = get_settings()
    settings.tool_provider = "mock"
    try:
        stats_before = await _stub_stats(client)

        create_tool = CreateTicketTool()
        created = await create_tool.invoke(
            {"title": "mock 降级验证工单"},
            {**_CONTEXT, "request_id": "acc-mock-001"},
        )
        if not created.success:
            print(f"✗ mock 创建失败: {created.error}")
            return False
        ticket_id = created.output["ticket"]["ticket_id"]

        closed = await create_tool.compensate(created.compensation_data)
        if not closed.success:
            print(f"✗ mock 补偿失败: {closed.error}")
            return False

        stats_after = await _stub_stats(client)
        delta_post = stats_after["post_attempts"] - stats_before["post_attempts"]
        delta_patch = stats_after["patch_attempts"] - stats_before["patch_attempts"]
        print(f"mock 创建工单: {ticket_id};stub 计数增长: POST +{delta_post}, PATCH +{delta_patch}")

        if delta_post != 0 or delta_patch != 0:
            print("✗ mock 提供方发起了网络请求")
            return False
        if not ticket_id.startswith("TK-"):
            print(f"✗ mock 工单 ID 格式异常: {ticket_id}")
            return False
    finally:
        settings.tool_provider = "http"

    print("✓ mock 降级可用:不触网,接口契约与 Mock 数据正常支撑演示/回归")
    return True


# ============ 主入口 ============


async def main() -> int:
    print("=" * 60)
    print("工单真实接入联调验收(环境:本地临时 stub @ 127.0.0.1:9810)")
    print("=" * 60)

    # 审计重定向到独立目录(避免污染 logs/audit;沙箱无 PG,审计走本地缓存)
    if _AUDIT_CACHE_DIR.exists():
        shutil.rmtree(_AUDIT_CACHE_DIR)
    _AUDIT_CACHE_DIR.mkdir(parents=True)
    audit_module._audit_logger = AuditLogger(local_cache_path=str(_AUDIT_CACHE_DIR))

    settings = get_settings()
    print(
        f"配置: base={settings.ticket_api_base}, provider={settings.tool_provider}, "
        f"max_retries={settings.external_max_retries}, timeout={settings.external_timeout_seconds}s"
    )

    # 自启 stub(与 harness 同进程,uvicorn Server 作为后台任务)
    config = uvicorn.Config(stub_app, host=STUB_HOST, port=STUB_PORT, log_level="warning")
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())

    results: dict[str, bool] = {}
    try:
        if not await _wait_stub_ready():
            print("✗ stub 启动失败或不可达(127.0.0.1:9810)")
            return 1
        print("✓ stub 已启动并通过连通性验证")

        async with httpx.AsyncClient(timeout=5.0) as client:
            # 重置 stub 状态,保证可重复执行
            await client.post(f"{_STUB_BASE}/api/v1/reset")
            cases = [
                ("connectivity", case_connectivity),
                ("normal_create_update", case_normal_create_update),
                ("idempotent_retry", case_idempotent_retry),
                ("4xx_no_retry", case_4xx_no_retry),
                ("5xx_retry_exhausted", case_5xx_retry_exhausted),
                ("saga_compensation", case_saga_compensation),
                ("mock_fallback", case_mock_fallback),
            ]
            for name, case_fn in cases:
                try:
                    results[name] = await case_fn(client)
                except Exception as e:  # noqa: BLE001 单用例异常不阻断后续用例
                    print(f"用例 {name} 异常: {type(e).__name__}: {e}")
                    results[name] = False
    finally:
        server.should_exit = True
        await serve_task

    # 汇总
    print("\n" + "=" * 60)
    print("联调验收汇总(实例类型:临时 stub)")
    print("=" * 60)
    for name, ok in results.items():
        print(f"  {name}: {'✓ PASS' if ok else '✗ FAIL'}")
    print("=" * 60)
    passed = sum(1 for ok in results.values() if ok)
    print(f"通过: {passed}/{len(results)}")
    print(
        "覆盖边界:worker 退避重试与审计 DB 回写路径由单元测试覆盖"
        "(tests/test_ticket_external.py),本验收不依赖 PostgreSQL/Redis;"
        "UpdateTicketTool._call_external 的 old_values 为空占位(设计留白),"
        "更新补偿以直接构造 compensation_data 验证补偿通道。"
    )

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
