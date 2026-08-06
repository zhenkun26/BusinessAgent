"""工单系统临时 stub(联调验收沙箱,ticket-system-integration 5.2)

用途:真实工单系统未采购到位前,用本 stub 充当契约一致的联调实例,
锁定 POST/PATCH 契约、幂等键语义与故障注入路径;真实系统到位后
按 acceptance.md 用例集重跑即可。

实现契约:
- POST /api/v1/tickets           创建工单(校验 Authorization;支持 Idempotency-Key 去重)
- PATCH /api/v1/tickets/{id}     更新/关闭工单/恢复旧值
- GET  /api/v1/tickets           列出已建工单(验收断言用)
- GET  /health                   连通性检查(免认证)
- GET  /api/v1/stats             请求计数(验收断言重试次数用,免认证)
- POST /api/v1/reset             清空工单与计数(免认证)

故障注入(经 title 标记,因工具入参 schema 会丢弃额外字段):
- title 含 "[FAULT:503]"            → 始终 503(不建单,验证退避重试耗尽)
- title 含 "[FAULT:400]"            → 始终 400(验证 4xx 立即失败)
- title 含 "[FAULT:CREATE_THEN_503]"→ 建单后返回 503(模拟"已建单但响应丢失",
                                      重试带同幂等键时由去重逻辑返回首次工单)

凭证:期望 token 读环境变量 TICKET_STUB_TOKEN(默认 stub-acceptance-token),
与注入工具的 TICKET_API_TOKEN 保持一致即可通过认证。

运行:
    python -m eval.ticket_stub_server            # 独立运行(端口 9810)
    python -m eval.run_ticket_acceptance         # 验收 harness(自启 stub)
"""

from __future__ import annotations

import os
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

STUB_HOST = "127.0.0.1"
STUB_PORT = 9810

app = FastAPI(title="ticket-stub", docs_url=None, redoc_url=None)

# ---- 内存状态(进程重启即丢,符合临时 stub 定位) ----
_tickets: dict[str, dict[str, Any]] = {}
_idem_store: dict[str, dict[str, Any]] = {}  # Idempotency-Key → 首次响应
_stats: dict[str, int] = {"post_attempts": 0, "patch_attempts": 0, "idempotent_hits": 0}
_seq = {"n": 0}


def _expected_token() -> str:
    return os.environ.get("TICKET_STUB_TOKEN", "stub-acceptance-token")


def _check_auth(request: Request) -> Optional[JSONResponse]:
    """校验 Bearer 凭证(与 http_adapter 的 Authorization 头契约一致)"""
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {_expected_token()}":
        return JSONResponse(status_code=401, content={"detail": "unauthorized"})
    return None


@app.get("/health")
async def health() -> dict[str, str]:
    """连通性检查(免认证)"""
    return {"status": "ok", "system": "ticket-stub"}


@app.get("/api/v1/stats")
async def stats() -> dict[str, Any]:
    """请求计数(验收断言重试/触网次数用)"""
    return {**_stats, "ticket_count": len(_tickets)}


@app.post("/api/v1/reset")
async def reset() -> dict[str, str]:
    """清空工单与计数"""
    _tickets.clear()
    _idem_store.clear()
    for key in _stats:
        _stats[key] = 0
    _seq["n"] = 0
    return {"status": "reset"}


@app.get("/api/v1/tickets")
async def list_tickets(request: Request) -> Any:
    """列出全部已建工单(验收断言用)"""
    auth_error = _check_auth(request)
    if auth_error:
        return auth_error
    return {"tickets": list(_tickets.values())}


@app.post("/api/v1/tickets")
async def create_ticket(request: Request) -> Any:
    """创建工单(幂等键去重 + title 标记故障注入)"""
    _stats["post_attempts"] += 1
    auth_error = _check_auth(request)
    if auth_error:
        return auth_error

    body = await request.json()
    idem_key = request.headers.get("Idempotency-Key")

    # 幂等去重:同键重复提交返回首次结果,不新建工单
    if idem_key and idem_key in _idem_store:
        _stats["idempotent_hits"] += 1
        return _idem_store[idem_key]

    title = body.get("title", "")
    if "[FAULT:503]" in title:
        return JSONResponse(status_code=503, content={"detail": "injected 5xx"})
    if "[FAULT:400]" in title:
        return JSONResponse(status_code=400, content={"detail": "injected 4xx"})

    _seq["n"] += 1
    ticket = {
        "ticket_id": f"TK-STUB{_seq['n']:04d}",
        "title": title,
        "description": body.get("description") or title,
        "customer_id": body.get("customer_id"),
        "priority": body.get("priority", "normal"),
        "category": body.get("category", "general"),
        "status": "open",
        "created_by": "stub",
        "created_at": "2026-08-06",
    }
    _tickets[ticket["ticket_id"]] = ticket
    response = {"ticket": ticket}
    if idem_key:
        _idem_store[idem_key] = response

    if "[FAULT:CREATE_THEN_503]" in title:
        # 模拟"已建单但响应丢失":客户端超时/5xx 重试时依赖幂等键去重
        return JSONResponse(status_code=503, content={"detail": "created but lost response"})
    return response


@app.patch("/api/v1/tickets/{ticket_id}")
async def update_ticket(ticket_id: str, request: Request) -> Any:
    """更新工单(状态/字段/关闭/恢复旧值,补偿通道同此端点)"""
    _stats["patch_attempts"] += 1
    auth_error = _check_auth(request)
    if auth_error:
        return auth_error

    ticket = _tickets.get(ticket_id)
    if ticket is None:
        return JSONResponse(status_code=404, content={"detail": f"ticket not found: {ticket_id}"})

    body = await request.json()
    for key, value in body.items():
        if key == "comment":
            ticket.setdefault("comments", []).append({"user": "stub", "text": value})
        else:
            ticket[key] = value
    return {"ticket": ticket}


def main() -> None:
    """独立运行入口:python -m eval.ticket_stub_server"""
    uvicorn.run(app, host=STUB_HOST, port=STUB_PORT, log_level="info")


if __name__ == "__main__":
    main()
