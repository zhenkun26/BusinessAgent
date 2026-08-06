"""统一外部 HTTP 适配器(外部系统接入,规格 5.2)

契约:
- httpx.AsyncClient 统一超时
- 5xx/网络异常 → 指数退避重试(默认 2 次)
- 401/403/4xx → 立即失败,不重试
- 返回 (success, data, error),由工具层归一化为 ToolResult
- 日志/错误信息不包含凭证与完整请求体
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx
from loguru import logger

from app.config import get_settings


async def call_external_api(
    method: str,
    url: str,
    *,
    api_token: Optional[str] = None,
    json_body: Optional[dict] = None,
    extra_headers: Optional[dict[str, str]] = None,
    timeout_seconds: Optional[float] = None,
    max_retries: Optional[int] = None,
    meta: Optional[dict[str, Any]] = None,
) -> tuple[bool, Any, Optional[str]]:
    """调用外部 HTTP API(统一超时/重试/错误归一化)

    Args:
        method: HTTP 方法(GET/POST/PATCH)
        url: 完整请求 URL
        api_token: Bearer 凭证(仅请求头发送,绝不入日志)
        json_body: JSON 请求体(可选)
        extra_headers: 额外请求头(可选)
        timeout_seconds: 超时秒数,默认读配置
        max_retries: 重试次数(不含首次),默认读配置
        meta: 可选输出参数,返回时写入 attempts(实际请求次数,含重试),
            供工具层记入 side_effects/审计(不影响既有调用方)

    Returns:
        (success, data, error):
        - success=True 时 data 为响应 JSON(或文本),error=None
        - success=False 时 data=None,error 为归一化错误信息
    """
    settings = get_settings()
    timeout = timeout_seconds or settings.external_timeout_seconds
    retries = max_retries if max_retries is not None else settings.external_max_retries
    headers = {"Accept": "application/json"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    if extra_headers:
        headers.update(extra_headers)

    last_error = "未知错误"
    attempt = 0
    while True:
        attempt += 1
        if meta is not None:
            meta["attempts"] = attempt
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method, url, headers=headers, json=json_body
                )

            if response.status_code in (401, 403):
                return False, None, (
                    f"外部系统认证失败(HTTP {response.status_code});"
                    f"请检查 {_host_label(url)} 的访问凭证配置"
                )
            if 400 <= response.status_code < 500:
                return False, None, (
                    f"外部系统请求被拒绝(HTTP {response.status_code}): "
                    f"{response.text[:200]}"
                )
            if response.status_code >= 500:
                if attempt <= retries:
                    await _backoff(attempt)
                    continue
                return False, None, (
                    f"外部系统服务不可用(HTTP {response.status_code}),"
                    f"已重试 {retries} 次"
                )

            # 2xx:尝试解析 JSON,失败则返回文本
            try:
                return True, response.json(), None
            except ValueError:
                return True, response.text, None

        except httpx.TimeoutException:
            last_error = f"外部系统请求超时(>{timeout}s)"
            if attempt <= retries:
                await _backoff(attempt)
                continue
            return False, None, f"{last_error},已重试 {retries} 次"
        except httpx.HTTPError as e:
            last_error = f"外部系统网络错误: {type(e).__name__}"
            if attempt <= retries:
                await _backoff(attempt)
                continue
            return False, None, f"{last_error},已重试 {retries} 次"


async def _backoff(attempt: int) -> None:
    """指数退避:1s, 2s, 4s..."""
    delay = min(2 ** (attempt - 1), 8)
    logger.warning(f"外部 API 调用失败,{delay}s 后重试(第 {attempt} 次)")
    await asyncio.sleep(delay)


def _host_label(url: str) -> str:
    """仅提取 host 用于错误提示(不含路径/凭证)"""
    try:
        parsed = httpx.URL(url)
        return parsed.host or url
    except Exception:  # noqa: BLE001
        return url
