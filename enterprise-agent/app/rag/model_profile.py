"""Production model contract and startup probes; no implicit downloads or fallbacks."""

from __future__ import annotations

import asyncio
import math
import re
from typing import Any
from urllib.parse import urlsplit

PROFILE = "bailian-deepseek-v1"
COLLECTION = "enterprise_knowledge_bailian_v4_1024_v1"
PROBE_TEXT = "Model startup check: the sample document is available."


def uses_remote_profile(settings: Any) -> bool:
    return settings.app_env == "prod" or getattr(settings, "model_profile", "") == PROFILE


def validate_model_profile(settings: Any) -> list[str]:
    """Configuration only: no imports of adapters, network access or filesystem writes."""
    if not uses_remote_profile(settings):
        return []
    errors: list[str] = []
    expected = {
        "model_profile": PROFILE,
        "embedding_provider": "bailian",
        "embedding_model": "text-embedding-v4",
        "embedding_dim": 1024,
        "reranker_provider": "bailian",
        "reranker_model": "qwen3-rerank",
        "llm_provider": "openai_compatible",
        "lite_llm_model": "deepseek-flash",
        "primary_llm_model": "deepseek-v4-pro",
        "milvus_collection": COLLECTION,
    }
    for field, value in expected.items():
        if getattr(settings, field, None) != value:
            errors.append(f"MODEL_CONFIG_{field.upper()}")
    for field in ("openai_api_key", "embedding_api_key", "reranker_api_key"):
        if not getattr(settings, field, "").strip():
            errors.append(f"MODEL_CONFIG_{field.upper()}")
    paths = {
        "embedding_base_url": "/compatible-mode/v1",
        "reranker_base_url": "/api/v1/services/rerank/text-rerank",
        "openai_base_url": "/v1",
    }
    for field, path in paths.items():
        try:
            url = urlsplit(getattr(settings, field, ""))
            host = url.hostname or ""
            valid_host = host == "api.deepseek.com" if field == "openai_base_url" else (
                host == "dashscope.aliyuncs.com"
                or bool(re.fullmatch(r"[a-z0-9-]+\.cn-beijing\.maas\.aliyuncs\.com", host))
            )
            valid_path = url.path.rstrip("/") == path or (
                field == "openai_base_url" and url.path in ("", "/"))
            if (not valid_host or not valid_path or url.scheme != "https"
                    or url.port not in (None, 443)
                    or url.username or url.password or url.query or url.fragment):
                errors.append(f"MODEL_CONFIG_{field.upper()}")
        except (ValueError, TypeError):
            errors.append(f"MODEL_CONFIG_{field.upper()}")
    if not 0 < settings.model_http_timeout_seconds <= 60:
        errors.append("MODEL_CONFIG_HTTP_TIMEOUT")
    if type(settings.model_http_max_retries) is not int or not 0 <= settings.model_http_max_retries <= 2:
        errors.append("MODEL_CONFIG_HTTP_RETRIES")
    return errors


def _check_vector(vector: Any, dimensions: int) -> None:
    if (len(vector) != dimensions or not all(math.isfinite(float(v)) for v in vector)
            or not any(float(v) != 0 for v in vector)):
        raise ValueError("MODEL_VECTOR_INVALID")


def _probe_remote_models(dimensions: int) -> None:
    from app.rag.embeddings import get_embeddings
    from app.rag.reranker import BailianReranker, get_reranker
    from app.rag.vector_store import SearchResult

    embeddings = get_embeddings()
    _check_vector(embeddings.embed_query(PROBE_TEXT), dimensions)
    documents = embeddings.embed_documents([PROBE_TEXT])
    if len(documents) != 1:
        raise ValueError("MODEL_DOCUMENT_VECTOR_INVALID")
    _check_vector(documents[0], dimensions)
    reranker = get_reranker()
    if not isinstance(reranker, BailianReranker):
        raise ValueError("MODEL_RERANKER_INVALID")
    candidate = SearchResult(
        chunk_id="model-startup", document_id="model-startup", title="Startup probe",
        content=PROBE_TEXT, score=1.0, dept_namespace="shared_company", doc_type="policy",
        source_url="", updated_at=0,
    )
    results = reranker.rerank(PROBE_TEXT, [candidate], top_n=1)
    if (len(results) != 1 or results[0].chunk_id != candidate.chunk_id
            or not math.isfinite(results[0].score)):
        raise ValueError("MODEL_RERANK_RESULT_INVALID")


async def _probe_llms() -> None:
    from app.rag.llm import get_llm_router

    router = get_llm_router()
    for llm in (router.get_primary(), router.get_cloud_lite()):
        if llm is None:
            raise ValueError("MODEL_LLM_MISSING")
        response = await asyncio.wait_for(
            llm.ainvoke("Reply with OK for this synthetic startup check.", max_tokens=32),
            timeout=90,
        )
        if not isinstance(response.content, str) or not response.content.strip():
            raise ValueError("MODEL_LLM_EMPTY")


async def verify_model_startup(settings: Any) -> None:
    """Fail before business initialization; development never performs these probes."""
    errors = validate_model_profile(settings)
    if errors:
        raise RuntimeError("MODEL_PROFILE_INVALID: " + ",".join(errors))
    if settings.app_env != "prod":
        return
    if not settings.model_startup_probes_enabled:
        raise RuntimeError("MODEL_STARTUP_PROBES_NOT_AUTHORIZED")
    try:
        await asyncio.to_thread(_probe_remote_models, settings.embedding_dim)
    except Exception:
        raise RuntimeError("MODEL_REMOTE_STARTUP_FAILED") from None
    try:
        await _probe_llms()
    except Exception:
        raise RuntimeError("MODEL_LLM_STARTUP_FAILED") from None
