"""Prompt 注册与版本管理(P2-1)

职责:
- get_prompt(name, user_id):按名称取当前生效模板,支持 A/B 确定性分流
- 进程内缓存:启动时 refresh_prompt_cache() 全量加载;管理 API 变更后立即刷新
  (同步节点 planner/aggregator 在线程池执行,不能跨事件循环访问 async DB,
   因此读取路径为纯同步缓存查询,DB 仅在 async 上下文刷新)
- 降级:缓存未命中(如 DB 不可用/启动失败)时回落 app.prompts.defaults(版本号 0)

A/B 分流:同 name 多个 active 版本时,按 md5(user_id:name) % 100 落入
各版本 traffic_weight 的累计区间;权重未覆盖的剩余流量归最低版本(对照组)。
"""

from __future__ import annotations

import hashlib
from contextvars import ContextVar
from typing import Optional

from loguru import logger
from sqlalchemy import text

from app.prompts.defaults import DEFAULT_PROMPTS

# 请求级用户标识(chat 入口设置;A/B 分流的兜底来源,调用点优先显式传 user_id)
_prompt_user_id: ContextVar[Optional[str]] = ContextVar("prompt_user_id", default=None)

# name -> list[{"version": int, "content": str, "traffic_weight": int}](按 version 升序)
_cache: dict[str, list[dict]] = {}


def set_prompt_user(user_id: Optional[str]):
    """设置当前请求的 prompt 分流用户(返回 token,用于 reset)"""
    return _prompt_user_id.set(user_id)


def reset_prompt_user(token) -> None:
    _prompt_user_id.reset(token)


def get_prompt(name: str, user_id: Optional[str] = None) -> tuple[str, int]:
    """获取 prompt 模板,返回 (content, version);version=0 表示代码默认降级"""
    if name not in DEFAULT_PROMPTS:
        raise KeyError(f"未知 prompt: {name}(未在 defaults 注册)")

    versions = _cache.get(name) or []
    if not versions:
        return DEFAULT_PROMPTS[name], 0

    if len(versions) == 1:
        return versions[0]["content"], versions[0]["version"]

    # A/B 确定性分流(同一用户同一名称永远命中同一版本)
    uid = user_id or _prompt_user_id.get() or "anonymous"
    h = int(hashlib.md5(f"{uid}:{name}".encode()).hexdigest(), 16) % 100
    cumulative = 0
    for v in versions:
        cumulative += int(v.get("traffic_weight") or 0)
        if h < cumulative:
            return v["content"], v["version"]
    # 权重未覆盖的流量归最低版本(对照组)
    return versions[0]["content"], versions[0]["version"]


async def refresh_prompt_cache() -> int:
    """从 DB 全量刷新 active 版本缓存,返回加载的 prompt 名称数

    失败时保留旧缓存(或空缓存→get_prompt 降级代码默认),不抛异常。
    """
    try:
        from app.core.database import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT name, version, content, traffic_weight "
                        "FROM prompt_versions WHERE status = 'active' "
                        "ORDER BY name, version"
                    )
                )
            ).mappings().all()

        new_cache: dict[str, list[dict]] = {}
        for r in rows:
            new_cache.setdefault(r["name"], []).append(
                {
                    "version": r["version"],
                    "content": r["content"],
                    "traffic_weight": r["traffic_weight"],
                }
            )
        _cache.clear()
        _cache.update(new_cache)
        logger.info(f"Prompt 缓存已刷新({len(new_cache)} 个名称)")
        return len(new_cache)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Prompt 缓存刷新失败(沿用旧缓存/代码默认): {e}")
        return 0


async def sync_prompt_defaults() -> None:
    """启动时把代码默认 prompt 作为 v1 写入(已存在则跳过,不覆盖人工修改)

    表不存在(未跑 migration)时告警并继续,get_prompt 全程降级代码默认。
    """
    try:
        from app.core.database import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            for name, content in DEFAULT_PROMPTS.items():
                await session.execute(
                    text(
                        "INSERT INTO prompt_versions "
                        "(name, version, content, status, traffic_weight, activated_at) "
                        "VALUES (:name, 1, :content, 'active', 100, CURRENT_TIMESTAMP) "
                        "ON CONFLICT (name, version) DO NOTHING"
                    ),
                    {"name": name, "content": content},
                )
            await session.commit()
        logger.info(f"Prompt 默认版本已同步({len(DEFAULT_PROMPTS)} 个)")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"prompt_versions 同步失败(降级用代码默认): {e}")
