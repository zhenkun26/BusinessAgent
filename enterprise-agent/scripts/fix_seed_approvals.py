"""一次性修复脚本:预置批量审批单(appr_batch_001/002/003)数据缺陷

问题(Bug 1):
1. requester_token 为 NULL → 经理批准后走 approved_pending_reauth,永远到不了 executed
2. prefill_payload 为扁平参数,缺动态建单的 {"tool_calls":[...]} 包装 → 批准后报
   "审批负载中无工具调用(prefill_payload.tool_calls 为空)"

修复:
- 用 app 自己的 JWTManager(读 .env 的 secret)为发起人 user_sales_001 签一个
  10 年过期的 token,写入三行的 requester_token
- 把 prefill_payload 重写为动态建单一致的 {"tool_calls":[{tool,params,reason}]} 格式

用法(在 enterprise-agent/ 目录下):
    python scripts/fix_seed_approvals.py

注意:init.sql 无法预置有效 JWT(签名密钥在 .env),重建数据库后需重跑本脚本。
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.core.database import close_db, init_db, get_session_factory
from app.security.jwt_manager import get_jwt_manager

REQUESTERS = {
    "sales": {
        "sub": "user_sales_001",
        "username": "销售员张三",
        "role": "salesperson",
        "department": "dept_sales",
    },
    "cs": {
        "sub": "user_cs_001",
        "username": "客服李四",
        "role": "customer_service",
        "department": "dept_cs",
    },
}

# 与动态建单(execution.py _create_approval)一致的 tool_calls 包装格式
# 注意:appr_batch_003 的 create_ticket 按 RBAC 仅 customer_service/manager 可用,
# 发起人必须是客服(user_cs_001),否则批准后工具执行被 RBAC 拒绝
FIXES = {
    "appr_batch_001": {
        "requester": "sales",
        "tool": "create_crm_task",
        "params": {
            "customer_id": "C001",
            "title": "Q3季度跟进",
            "description": "客户 C001 季度跟进回访",
            "priority": 1,
        },
        "reason": "为客户 C001 创建季度跟进任务",
    },
    "appr_batch_002": {
        "requester": "sales",
        "tool": "send_email_internal",
        "params": {
            "to": ["zhaoliu@company.internal"],
            "subject": "C001跟进安排",
            "body": "关于客户 C001 的季度跟进安排,请知悉。",
        },
        "reason": "通知经理赵六关于 C001 的跟进安排",
    },
    "appr_batch_003": {
        "requester": "cs",
        "tool": "create_ticket",
        "params": {
            "title": "C001售后协调",
            "description": "客户 C001 售后协调工单",
            "customer_id": "C001",
            "priority": "high",
        },
        "reason": "为 C001 创建售后协调工单",
    },
}


async def main() -> None:
    await init_db()
    try:
        jwt_mgr = get_jwt_manager()
        now = datetime.now(timezone.utc)
        tokens = {
            key: jwt_mgr.encode({**req, "exp": now + timedelta(days=3650), "iat": now})
            for key, req in REQUESTERS.items()
        }

        factory = get_session_factory()
        async with factory() as session:
            for aid, fix in FIXES.items():
                requester = REQUESTERS[fix["requester"]]
                payload = {"tool_calls": [{k: fix[k] for k in ("tool", "params", "reason")}]}
                result = await session.execute(
                    text(
                        "UPDATE approval_requests "
                        "SET requester_id = :uid, requester_token = :token, "
                        "prefill_payload = CAST(:payload AS JSONB) "
                        "WHERE approval_id = :aid"
                    ),
                    {
                        "uid": requester["sub"],
                        "token": tokens[fix["requester"]],
                        "payload": json.dumps(payload, ensure_ascii=False),
                        "aid": aid,
                    },
                )
                print(f"{aid}: 更新 {result.rowcount} 行 (requester={requester['sub']})")
            await session.commit()

        # 验证
        async with factory() as session:
            rows = (await session.execute(
                text(
                    "SELECT approval_id, requester_token IS NOT NULL AS has_token, "
                    "prefill_payload->'tool_calls' IS NOT NULL AS has_tool_calls "
                    "FROM approval_requests WHERE approval_id IN ('appr_batch_001','appr_batch_002','appr_batch_003')"
                )
            )).fetchall()
            for r in rows:
                print(f"验证 {r.approval_id}: has_token={r.has_token}, has_tool_calls={r.has_tool_calls}")
        for key, tk in tokens.items():
            print(f"token[{key}] 未过期: {not jwt_mgr.is_expired(tk)}")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
