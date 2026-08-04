"""Prompt 版本管理 API(P2-1)

仅 admin / manager 角色可用。模板语法约定:Python str.format,
JSON 示例花括号必须 {{ }} 转义(与代码内默认 prompt 一致)。

变更语义:
- 新建版本:draft 状态,不生效
- 激活:active 并默认归档同名人其他 active 版本(回滚 = 激活旧版本号)
- A/B:activate(archive_others=false) 让两个版本同时 active,
  再用 /traffic 分配权重(0-100,未覆盖流量归最低版本)
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.database import get_db
from app.observability.audit import get_audit_logger
from app.prompts.defaults import DEFAULT_PROMPTS
from app.prompts.registry import refresh_prompt_cache
from app.security.rbac import AgentRole, User, require_roles

router = APIRouter()

# 仅 admin / manager
_authorized = Depends(require_roles(AgentRole.ADMIN, AgentRole.MANAGER))


class CreateVersionRequest(BaseModel):
    content: str = Field(..., min_length=1, description="模板原文(str.format 语法)")


class ActivateRequest(BaseModel):
    version: int = Field(..., ge=1)
    archive_others: bool = Field(
        True, description="是否归档同名人其他 active 版本(A/B 时传 false)"
    )


class TrafficRequest(BaseModel):
    weights: dict[int, int] = Field(
        ..., description="版本号 → 流量权重(0-100),仅 active 版本"
    )


def _check_name(name: str) -> None:
    if name not in DEFAULT_PROMPTS:
        raise HTTPException(404, f"未知 prompt: {name}")


@router.get("/prompts")
async def list_prompts(user: User = _authorized, db=Depends(get_db)):
    """列出全部 prompt 及其版本(含状态/流量权重)"""
    rows = (
        await db.execute(
            text(
                "SELECT name, version, status, traffic_weight, created_by, "
                "created_at, activated_at, LEFT(content, 80) AS preview "
                "FROM prompt_versions ORDER BY name, version"
            )
        )
    ).mappings().all()

    prompts: dict[str, list[dict]] = {name: [] for name in DEFAULT_PROMPTS}
    for r in rows:
        prompts.setdefault(r["name"], []).append(
            {
                "version": r["version"],
                "status": r["status"],
                "traffic_weight": r["traffic_weight"],
                "created_by": r["created_by"],
                "created_at": str(r["created_at"]),
                "activated_at": str(r["activated_at"]) if r["activated_at"] else None,
                "preview": r["preview"],
            }
        )
    return {"prompts": prompts}


@router.get("/prompts/{name}/versions/{version}")
async def get_prompt_version(
    name: str, version: int, user: User = _authorized, db=Depends(get_db)
):
    """查看指定版本完整内容"""
    _check_name(name)
    row = (
        (
            await db.execute(
                text(
                    "SELECT name, version, content, status, traffic_weight "
                    "FROM prompt_versions WHERE name = :name AND version = :version"
                ),
                {"name": name, "version": version},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, f"prompt {name} v{version} 不存在")
    return dict(row)


@router.post("/prompts/{name}/versions")
async def create_version(
    name: str,
    req: CreateVersionRequest,
    user: User = _authorized,
    db=Depends(get_db),
):
    """新建 draft 版本(不生效,需 activate)"""
    _check_name(name)
    row = (
        (
            await db.execute(
                text("SELECT COALESCE(MAX(version), 0) + 1 AS v FROM prompt_versions WHERE name = :name"),
                {"name": name},
            )
        )
        .mappings()
        .first()
    )
    new_version = row["v"]
    await db.execute(
        text(
            "INSERT INTO prompt_versions (name, version, content, status, created_by) "
            "VALUES (:name, :version, :content, 'draft', :uid)"
        ),
        {"name": name, "version": new_version, "content": req.content, "uid": user.user_id},
    )
    await db.commit()

    await get_audit_logger().log(
        event_type="prompt_change",
        user_id=user.user_id,
        payload={"action": "create_draft", "name": name, "version": new_version},
    )
    return {"name": name, "version": new_version, "status": "draft"}


@router.post("/prompts/{name}/activate")
async def activate_version(
    name: str,
    req: ActivateRequest,
    user: User = _authorized,
    db=Depends(get_db),
):
    """激活指定版本(回滚 = 激活旧版本号)

    archive_others=true(默认):同名人其他 active 版本归档,本版本权重 100
    archive_others=false:本版本以权重 0 加入 active 组,配合 /traffic 做 A/B
    """
    _check_name(name)
    exists = (
        (
            await db.execute(
                text(
                    "SELECT 1 FROM prompt_versions WHERE name = :name AND version = :version"
                ),
                {"name": name, "version": req.version},
            )
        )
        .first()
    )
    if not exists:
        raise HTTPException(404, f"prompt {name} v{req.version} 不存在")

    if req.archive_others:
        await db.execute(
            text(
                "UPDATE prompt_versions SET status = 'archived' "
                "WHERE name = :name AND status = 'active' AND version != :version"
            ),
            {"name": name, "version": req.version},
        )
        weight = 100
    else:
        weight = 0

    await db.execute(
        text(
            "UPDATE prompt_versions SET status = 'active', traffic_weight = :weight, "
            "activated_at = CURRENT_TIMESTAMP "
            "WHERE name = :name AND version = :version"
        ),
        {"name": name, "version": req.version, "weight": weight},
    )
    await db.commit()
    await refresh_prompt_cache()

    await get_audit_logger().log(
        event_type="prompt_change",
        user_id=user.user_id,
        payload={
            "action": "activate",
            "name": name,
            "version": req.version,
            "archive_others": req.archive_others,
        },
    )
    return {"name": name, "version": req.version, "status": "active", "traffic_weight": weight}


@router.put("/prompts/{name}/traffic")
async def set_traffic(
    name: str,
    req: TrafficRequest,
    user: User = _authorized,
    db=Depends(get_db),
):
    """设置 A/B 流量权重(仅 active 版本;权重和 ≤100,剩余归最低版本)"""
    _check_name(name)
    if not req.weights:
        raise HTTPException(400, "weights 不能为空")
    for version, weight in req.weights.items():
        if not 0 <= weight <= 100:
            raise HTTPException(400, f"权重必须在 0-100: v{version}={weight}")

    active = (
        (
            await db.execute(
                text(
                    "SELECT version FROM prompt_versions WHERE name = :name AND status = 'active'"
                ),
                {"name": name},
            )
        )
        .scalars()
        .all()
    )
    active_set = {int(v) for v in active}
    unknown = set(req.weights) - active_set
    if unknown:
        raise HTTPException(400, f"版本不是 active 状态: {sorted(unknown)}")

    for version, weight in req.weights.items():
        await db.execute(
            text(
                "UPDATE prompt_versions SET traffic_weight = :weight "
                "WHERE name = :name AND version = :version"
            ),
            {"name": name, "version": version, "weight": weight},
        )
    await db.commit()
    await refresh_prompt_cache()

    await get_audit_logger().log(
        event_type="prompt_change",
        user_id=user.user_id,
        payload={"action": "set_traffic", "name": name, "weights": req.weights},
    )
    return {"name": name, "weights": req.weights}
