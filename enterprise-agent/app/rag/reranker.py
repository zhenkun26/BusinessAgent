"""Reranker(两阶段检索的精排层)

策略(按 .env RERANKER_PROVIDER 选择):
- local_bge: 本地 bge-reranker-large(免费,推荐,需 sentence-transformers)
- cohere: Cohere Rerank(rerank-multilingual-v3.0,需 API Key)
- llm: LLM 打分降级(本地 Ollama,慢但通用)
- passthrough: 不重排(仅粗排顺序)

返回结果按 score 降序,只保留 top_n 条。
"""

from typing import Optional

from loguru import logger

from app.config import get_settings
from app.rag.vector_store import SearchResult


class Reranker:
    """Reranker 抽象"""

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_n: int = 5,
    ) -> list[SearchResult]:
        raise NotImplementedError


class BgeLocalReranker(Reranker):
    """本地 bge-reranker-large(免费,推荐)

    用 sentence-transformers 加载 CrossEncoder,对 (query, content) 打分。
    模型路径由 .env RERANKER_MODEL 指定(如 D:/models/bge-reranker-large)。
    """

    def __init__(self):
        s = get_settings()
        from sentence_transformers import CrossEncoder

        from app.rag.embeddings import _detect_device

        self._model_path = s.reranker_model
        device = _detect_device()
        self._ce = CrossEncoder(self._model_path, max_length=512, device=device)
        logger.info(f"本地 BGE Reranker 已加载: {self._model_path}, device={device}")

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_n: int = 5,
    ) -> list[SearchResult]:
        if not candidates:
            return []

        # 构造 (query, content) 对
        pairs = [(query, c.content[:1000]) for c in candidates]
        scores = self._ce.predict(pairs)

        # 归一化到 [0, 1](CrossEncoder 输出 logits,用 sigmoid)
        import math

        scored: list[tuple[float, SearchResult]] = []
        for i, s in enumerate(scores):
            prob = 1.0 / (1.0 + math.exp(-float(s)))
            scored.append((prob, candidates[i]))

        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[SearchResult] = []
        for prob, c in scored[:top_n]:
            out.append(
                SearchResult(
                    chunk_id=c.chunk_id,
                    document_id=c.document_id,
                    title=c.title,
                    content=c.content,
                    score=prob,
                    dept_namespace=c.dept_namespace,
                    doc_type=c.doc_type,
                    source_url=c.source_url,
                    updated_at=c.updated_at,
                )
            )
        return out


class CohereReranker(Reranker):
    """Cohere Rerank(优先)"""

    def __init__(self):
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
        if not candidates:
            return []

        from langchain_cohere import CohereRerank

        reranker = CohereRerank(
            cohere_api_key=self._api_key,
            model=self._model,
            top_n=top_n,
        )

        # Cohere 接收 list[str],返回 index + relevance_score
        docs = [c.content for c in candidates]
        compressed = reranker.rerank_documents(docs, query)

        # 按 compressed 中的 score 重排
        out: list[SearchResult] = []
        for item in compressed:
            # langchain_cohere 返回 dict-like,含 'relevance_score' 和 index
            idx = item.get("index") if isinstance(item, dict) else getattr(item, "index", None)
            score = (
                item.get("relevance_score")
                if isinstance(item, dict)
                else getattr(item, "relevance_score", None)
            )
            if idx is None or idx >= len(candidates):
                continue
            original = candidates[idx]
            out.append(
                SearchResult(
                    chunk_id=original.chunk_id,
                    document_id=original.document_id,
                    title=original.title,
                    content=original.content,
                    score=float(score) if score is not None else original.score,
                    dept_namespace=original.dept_namespace,
                    doc_type=original.doc_type,
                    source_url=original.source_url,
                    updated_at=original.updated_at,
                )
            )
        # 截断 top_n
        return out[:top_n]


class LLMReranker(Reranker):
    """LLM 打分降级(无 bge-reranker/Cohere 时)

    让 LLM 对每个 (query, chunk) 对打 0-10 分,归一化为 0-1。
    用本地小模型(qwen3.5:4b),免费且高频适合。
    仅在 bge-reranker 不可用时降级使用(慢但通用)。
    """

    def __init__(self, llm=None):
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
        if not candidates:
            return []

        from langchain_core.prompts import ChatPromptTemplate

        from app.prompts import get_prompt

        sys_tpl, _sv = get_prompt("reranker_llm_score_system")
        human_tpl, _hv = get_prompt("reranker_llm_score_human")
        prompt = ChatPromptTemplate.from_messages(
            [("system", sys_tpl), ("human", human_tpl)]
        )

        chain = prompt | self._llm

        scored: list[tuple[float, SearchResult]] = []
        for c in candidates:
            try:
                resp = chain.invoke({"query": query, "text": c.content[:1000]})
                text = resp.content if hasattr(resp, "content") else str(resp)
                # 提取首个整数
                num_str = "".join(ch for ch in text if ch.isdigit())[:2]
                score_int = int(num_str) if num_str else 0
                score_int = max(0, min(10, score_int))
                scored.append((score_int / 10.0, c))
            except Exception as e:  # noqa: BLE001
                logger.warning(f"LLM 打分失败,沿用原分数: {e}")
                scored.append((c.score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            SearchResult(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                title=c.title,
                content=c.content,
                score=s,
                dept_namespace=c.dept_namespace,
                doc_type=c.doc_type,
                source_url=c.source_url,
                updated_at=c.updated_at,
            )
            for s, c in scored[:top_n]
        ]


class PassthroughReranker(Reranker):
    """无 Rerank(直接用召回分数)"""

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_n: int = 5,
    ) -> list[SearchResult]:
        return candidates[:top_n]


# ============ 工厂 ============


_reranker: Optional[Reranker] = None


def get_reranker() -> Reranker:
    """获取 Reranker 单例(按 .env RERANKER_PROVIDER 选择)

    优先级:
    1. local_bge: 本地 bge-reranker-large(免费,推荐)
    2. cohere: Cohere Rerank(需 API Key)
    3. llm: LLM 打分(本地 Ollama)
    4. passthrough: 不重排
    """
    global _reranker
    if _reranker is not None:
        return _reranker

    s = get_settings()
    provider = s.reranker_provider.lower()

    if provider == "local_bge":
        try:
            _reranker = BgeLocalReranker()
            logger.info(f"Reranker 后端: local_bge ({s.reranker_model})")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"本地 BGE Reranker 初始化失败,降级 Passthrough: {e}")
            _reranker = PassthroughReranker()
    elif provider == "cohere" or (provider == "auto" and s.cohere_api_key):
        try:
            _reranker = CohereReranker()
            logger.info("Reranker 后端: Cohere")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Cohere 初始化失败,降级 Passthrough: {e}")
            _reranker = PassthroughReranker()
    elif provider == "llm":
        try:
            _reranker = LLMReranker()
            logger.info("Reranker 后端: LLM(本地 Ollama)")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"LLM Reranker 初始化失败,降级 Passthrough: {e}")
            _reranker = PassthroughReranker()
    else:
        _reranker = PassthroughReranker()
        logger.info("Reranker 后端: Passthrough(不重排)")

    return _reranker
