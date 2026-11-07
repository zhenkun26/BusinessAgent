"""Reranker(两阶段检索的精排层)

策略(按 .env RERANKER_PROVIDER 选择):
- bailian: selected Beijing qwen3-rerank profile; failures do not select passthrough
- local_bge: 本地 bge-reranker-large(免费,推荐,需 sentence-transformers)
- cohere: Cohere Rerank(rerank-multilingual-v3.0,需 API Key)
- llm: LLM 打分降级(本地 Ollama,慢但通用)
- passthrough: 不重排(仅粗排顺序)

返回结果按 score 降序,只保留 top_n 条。
"""

from concurrent.futures import CancelledError
from dataclasses import dataclass, replace
import hashlib
import json
from typing import Optional

from loguru import logger

from app.config import get_settings
from app.core.execution_budget import ExecutionBudgetExceeded, check_execution_budget
from app.rag.vector_store import SearchResult
from app.rag.model_profile import uses_remote_profile, validate_model_profile


@dataclass(frozen=True)
class RerankerSelection:
    """Internal fixed selection metadata; never contains credentials or model text."""

    requested_provider: str
    effective_provider: str
    reason: str = "none"


class Reranker:
    """Reranker 抽象"""

    performs_rerank = True

    def __init__(self, provider: str = "injected") -> None:
        self.selection = RerankerSelection(provider, provider)
        self._configuration_binding: Optional[str] = None

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_n: int = 5,
    ) -> list[SearchResult]:
        raise NotImplementedError


class BailianReranker(Reranker):
    """Beijing qwen3-rerank; preserve source metadata and reject invalid results."""

    def __init__(self) -> None:
        super().__init__("bailian")
        from app.rag.remote_models import BailianClient

        s = get_settings()
        self._model = s.reranker_model
        self._client = BailianClient(
            s.reranker_base_url, s.reranker_api_key, s.model_http_timeout_seconds,
            s.model_http_max_retries, kind="reranker",
        )

    def rerank(self, query: str, candidates: list[SearchResult],
               top_n: int = 5) -> list[SearchResult]:
        rows = self._client.rerank(query, [c.content for c in candidates], self._model, top_n)
        return [replace(candidates[index], score=score) for index, score in rows]


class BgeLocalReranker(Reranker):
    """本地 bge-reranker-large(免费,推荐)

    用 sentence-transformers 加载 CrossEncoder,对 (query, content) 打分。
    模型路径由 .env RERANKER_MODEL 指定(如 D:/models/bge-reranker-large)。
    """

    def __init__(self) -> None:
        super().__init__("local_bge")
        s = get_settings()
        from sentence_transformers import CrossEncoder

        from app.rag.embeddings import _detect_device

        self._model_path = s.reranker_model
        device = _detect_device()
        self._ce = CrossEncoder(
            self._model_path, max_length=512, device=device,
            local_files_only=s.app_env == "prod", trust_remote_code=False,
        )
        logger.info("RERANKER_LOCAL_INITIALIZED")

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_n: int = 5,
    ) -> list[SearchResult]:
        from concurrent.futures import CancelledError
        from app.core.execution_budget import ExecutionBudgetExceeded, check_execution_budget
        from app.security.rerank_results import OptionalRerankError, bge_scores, candidate_texts

        try:
            texts = candidate_texts(query, candidates, top_n)
            if not texts:
                return []
            pairs = [(query, text[:1000]) for text in texts]
            check_execution_budget()
            values = self._ce.predict(pairs)
            rows = bge_scores(values, len(candidates), top_n)
            check_execution_budget()
            return [replace(candidates[index], score=score,
                            access_roles=list(candidates[index].access_roles))
                    for index, score in rows]
        except (ExecutionBudgetExceeded, CancelledError):
            raise
        except Exception:
            check_execution_budget()
            raise OptionalRerankError() from None


class CohereReranker(Reranker):
    """Optional Cohere scoring; selected explicitly or by auto with credentials."""

    def __init__(self) -> None:
        super().__init__("cohere")
        s = get_settings()
        if not s.cohere_api_key:
            raise ValueError("COHERE_API_KEY 未配置")
        self._api_key = s.cohere_api_key
        self._model = s.cohere_rerank_model

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_n: int = 5,
    ) -> list[SearchResult]:
        from concurrent.futures import CancelledError
        from app.core.execution_budget import ExecutionBudgetExceeded, check_execution_budget
        from app.security.rerank_results import OptionalRerankError, candidate_texts, cohere_scores

        try:
            docs = candidate_texts(query, candidates, top_n)
            if not docs:
                return []
            from langchain_cohere import CohereRerank

            reranker = CohereRerank(
                cohere_api_key=self._api_key,
                model=self._model,
                top_n=top_n,
            )
            check_execution_budget()
            compressed = reranker.rerank_documents(docs, query)
            rows = cohere_scores(compressed, len(candidates), top_n)
            check_execution_budget()
            return [replace(candidates[index], score=score,
                            access_roles=list(candidates[index].access_roles))
                    for index, score in rows]
        except (ExecutionBudgetExceeded, CancelledError):
            raise
        except Exception:
            check_execution_budget()
            raise OptionalRerankError() from None


class LLMReranker(Reranker):
    """Optional development scoring; any invalid score rejects the entire batch."""

    def __init__(self, llm=None) -> None:
        super().__init__("llm")
        if llm is None:
            from app.rag.llm import get_local_llm

            llm = get_local_llm()
        self._llm = llm

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_n: int = 5,
    ) -> list[SearchResult]:
        from concurrent.futures import CancelledError
        from app.core.execution_budget import ExecutionBudgetExceeded, check_execution_budget
        from app.prompts import get_prompt
        from app.security.rerank_boundary import RerankBoundaryError, build_prompt, model_score

        try:
            check_execution_budget()
            if type(top_n) is not int or top_n < 1:
                raise RerankBoundaryError()
            if not candidates:
                return []
            sys_tpl, sv = get_prompt("reranker_llm_score_system")
            human_tpl, hv = get_prompt("reranker_llm_score_human")
            scored: list[tuple[float, SearchResult]] = []
            for candidate in candidates:
                prompt = build_prompt(sys_tpl, sv, human_tpl, hv, query, candidate.content)
                response = self._llm.invoke(prompt.messages(), config=prompt.config())
                scored.append((model_score(response), candidate))
            check_execution_budget()
            scored.sort(key=lambda item: item[0], reverse=True)
            return [replace(c, score=score, access_roles=list(c.access_roles))
                    for score, c in scored[:top_n]]
        except (ExecutionBudgetExceeded, CancelledError):
            raise
        except Exception:
            check_execution_budget()
            logger.warning("RERANKER_MODEL_SCORE_FAILED")
            raise RerankBoundaryError() from None


class PassthroughReranker(Reranker):
    """无 Rerank(直接用召回分数)"""

    performs_rerank = False

    def __init__(self) -> None:
        super().__init__("passthrough")
        self.selection = replace(self.selection, reason="disabled")

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_n: int = 5,
    ) -> list[SearchResult]:
        return candidates[:top_n]


# ============ 工厂 ============


_reranker: Optional[Reranker] = None


_PROVIDERS = frozenset({"bailian", "local_bge", "cohere", "llm", "passthrough", "auto"})


def _admit_configuration() -> tuple[str, bool, str]:
    """Validate before cache access; bind relevant settings without exposing their values."""
    settings = get_settings()
    provider = settings.reranker_provider
    if type(provider) is not str or provider.lower() not in _PROVIDERS:
        raise RuntimeError("RERANKER_CONFIGURATION_INVALID")
    provider = provider.lower()
    remote = uses_remote_profile(settings)
    if remote and validate_model_profile(settings):
        raise RuntimeError("MODEL_PROFILE_INVALID")
    fields = ["app_env", "model_profile"]
    if provider == "bailian":
        fields += ["reranker_model", "reranker_api_key", "reranker_base_url",
                   "model_http_timeout_seconds", "model_http_max_retries"]
    elif provider == "local_bge":
        fields += ["reranker_model", "local_model_device"]
    elif provider in {"cohere", "auto"}:
        fields += ["cohere_api_key", "cohere_rerank_model"]
    elif provider == "llm":
        fields += ["local_llm_model", "local_llm_base_url"]
    values = [provider, remote, *[getattr(settings, field, None) for field in fields]]
    binding = hashlib.sha256(json.dumps(values, ensure_ascii=True).encode()).hexdigest()
    return provider, remote, binding


def get_reranker() -> Reranker:
    """Reuse one configuration-bound backend; changes require process restart.

    Auto selects Cohere with a key, otherwise passthrough. Optional initialization
    failure selects passthrough once; no retry chain or implicit recovery is performed.
    """
    global _reranker
    check_execution_budget()
    provider, remote, binding = _admit_configuration()
    if _reranker is not None:
        if _reranker._configuration_binding != binding:
            raise RuntimeError("RERANKER_CONFIGURATION_CHANGED")
        check_execution_budget()
        return _reranker

    effective = provider
    reason = "none"
    if provider == "auto":
        effective = "cohere" if get_settings().cohere_api_key else "passthrough"
        if effective == "passthrough":
            reason = "auto_no_credentials"
    elif provider == "passthrough":
        reason = "disabled"

    constructors = {"bailian": BailianReranker, "local_bge": BgeLocalReranker,
                    "cohere": CohereReranker, "llm": LLMReranker,
                    "passthrough": PassthroughReranker}
    try:
        check_execution_budget()
        candidate = constructors[effective]()
    except (ExecutionBudgetExceeded, CancelledError):
        raise
    except Exception:
        check_execution_budget()
        if remote or effective == "bailian":
            raise RuntimeError("MODEL_RERANKER_LOAD_FAILED") from None
        if effective == "passthrough":
            raise RuntimeError("RERANKER_INITIALIZATION_FAILED") from None
        logger.warning("RERANKER_INITIALIZATION_FAILED")
        candidate = PassthroughReranker()
        effective, reason = "passthrough", "initialization_failed"

    check_execution_budget()
    if _admit_configuration() != (provider, remote, binding):
        raise RuntimeError("RERANKER_CONFIGURATION_CHANGED")
    candidate.selection = RerankerSelection(provider, effective, reason)
    candidate._configuration_binding = binding
    check_execution_budget()
    _reranker = candidate
    logger.info("RERANKER_SELECTED")
    return _reranker
