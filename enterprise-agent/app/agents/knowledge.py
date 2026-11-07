"""KnowledgeAgent:企业知识库检索 Agent(对应 v3 方案 6.4 节)

W3 完整实现：
- EnterpriseRAGRetriever 两阶段检索(向量召回 + Rerank)
- DegradationChain Milvus 三级降级(向量 → 关键词扫描 → PG 全文/ILIKE)
- ConfidenceDecider 场景化阈值(P1-2)
- LLM 生成答案(DeepSeek/OpenAI 兼容)
- 答案附来源(可追溯)

输出契约：AgentResult
- success: 检索 + 生成是否成功
- confidence: 综合置信度(检索分 + LLM 自评)
- output: {answer, coverage, hint, stage}
- sources: 检索来源列表
- needs_replan: 是否需要重规划(P1-3，知识库覆盖不足时触发)
"""

import time
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from app.rag.confidence import ConfidenceDecider, Coverage
from app.rag.degradation import DegradationChain
from app.rag.llm import get_lite_llm, get_local_llm
from app.rag.retriever import EnterpriseRAGRetriever
from app.rag.vector_store import SearchResult
from app.security.rbac import AgentRole
from app.security.retrieval_policy import resolve_scope


class RetrievalSource(BaseModel):
    """RAG 检索来源(对外契约)"""

    document_id: str
    chunk_id: str
    title: str
    source_url: Optional[str] = None
    updated_at: datetime
    score: float = Field(description="相关性得分 0-1")
    namespace: str


class AgentResult(BaseModel):
    """Agent 输出标准契约"""

    agent_name: str
    success: bool
    confidence: float = Field(ge=0, le=1)
    output: dict
    sources: list[RetrievalSource] = Field(default_factory=list)
    error: Optional[str] = None
    tokens_used: int = 0
    latency_ms: int = 0
    needs_replan: bool = False
    replan_reason: Optional[str] = None
    replan_hint: Optional[dict] = None


# Prompt 统一从注册表获取(P2-1:版本管理/A/B;代码默认值见 app/prompts/defaults.py)
from app.prompts import get_prompt


class KnowledgeAgent:
    """企业知识库检索 Agent

    对应 v3 方案 6.4 节 knowledge_agent_with_confidence
    """

    def __init__(
        self,
        user_role: AgentRole,
        user_dept: str,
        top_k: int = 10,
        rerank_top_k: int = 5,
        retriever: Optional[EnterpriseRAGRetriever] = None,
        decider: Optional[ConfidenceDecider] = None,
        llm=None,
    ):
        self.user_role = user_role
        self.user_dept = user_dept
        self.top_k = top_k
        self.rerank_top_k = rerank_top_k

        # 依赖注入(便于测试);默认从工厂取
        self.retriever = retriever or EnterpriseRAGRetriever(
            top_k=top_k, rerank_top_n=rerank_top_k
        )
        self.decider = decider or ConfidenceDecider()
        self.llm = llm  # 懒加载,避免无 LLM 时初始化失败
        self._eval_llm = None  # 自评用 LLM(本地小模型,懒加载)

        # 包装降级链
        self.degradation_chain = DegradationChain(self.retriever)

    def _get_llm(self):
        if self.llm is None:
            self.llm = get_lite_llm()
        return self.llm

    def _get_eval_llm(self):
        """获取自评用 LLM(本地 qwen3.5:4b,ChatOllama+reasoning=False，零云端成本)

        答案自评任务简单(打 0-10 分)，本地小模型足够，省云端调用。
        注意：必须用 ChatOllama+reasoning=False 关思考；ChatOpenAI 走 /v1 端点时
        extra_body={"think": False} 会被 Ollama 忽略(实测自评单次 44-94s);
        本地不可用时降级用 primary(保证可用)。
        """
        if self._eval_llm is None:
            try:
                self._eval_llm = get_local_llm()
            except Exception as e:  # noqa: BLE001
                from app.core.execution_budget import check_execution_budget
                check_execution_budget()
                logger.warning("KNOWLEDGE_LOCAL_MODEL_UNAVAILABLE")
                self._eval_llm = self._get_llm()
        return self._eval_llm

    async def run(self, query: str, history: Optional[list[dict]] = None) -> AgentResult:
        """执行 RAG 检索 + 生成

        Args:
            query: 子任务描述(用户消息)
            history: 多轮对话历史 [{"user","assistant"}]，用于：
                1) 指代消解：query 含"它/这/那"等指代词时，检索 query 拼接上一轮用户消息
                2) Generation: history stays in the untrusted JSON data envelope.
        """
        start = time.time()

        try:
            scope = resolve_scope(self.user_role, self.user_dept)
            # 1. 降级链检索(向量 → 关键词扫描 → PG 全文/ILIKE)
            # 检索用扩展后的 query(embedding 需要完整语义);自评/日志仍用原 query
            from app.graph.history import expand_query_with_history

            retrieval_query = expand_query_with_history(query, history)
            deg_result = await self.degradation_chain.run(
                query=retrieval_query,
                user_role=self.user_role.value if hasattr(self.user_role, "value") else str(self.user_role),
                dept_namespace=self.user_dept,
                top_k=self.rerank_top_k,
            )

            if deg_result.error:
                raise RuntimeError('RETRIEVAL_UNAVAILABLE')

            results = [result for result in deg_result.results if scope.allows_result(result)]
            stage = deg_result.stage

            if not results:
                # 知识库无结果,标记 needs_replan(P1-3)
                logger.warning("KNOWLEDGE_NO_RESULTS")
                return AgentResult(
                    agent_name="knowledge",
                    success=False,
                    confidence=0.0,
                    output={
                        "answer": "未在知识库中找到相关信息。",
                        "coverage": Coverage.NONE.value,
                        "stage": stage,
                    },
                    sources=[],
                    latency_ms=int((time.time() - start) * 1000),
                    needs_replan=True,
                    replan_reason="knowledge_coverage_none",
                    replan_hint={"query": query, "stage": stage},
                )

            from app.rag.score_admission import check_result_scores
            check_result_scores(results)

            # 2. LLM 生成答案(带多轮历史)
            # I-07:token 走统一采集通道(callback 累加器),不再自行提取 usage_metadata
            from app.observability.token_usage import snapshot_total_tokens

            tokens_before = snapshot_total_tokens()
            answer, llm_self_score = await self._generate_answer(query, results, history=history)
            check_result_scores(results)
            tokens = snapshot_total_tokens() - tokens_before

            # 3. 综合置信度(检索分 + LLM 自评 加权)
            top_score = results[0].score
            scene = ConfidenceDecider.detect_scene(query)
            combined_score = ConfidenceDecider.combine_score(
                retrieval_score=top_score,
                llm_self_score=llm_self_score,
                retrieval_weight=0.6,
            )

            # 4. 决策
            decision = self.decider.decide(score=combined_score, scene=scene)

            # 5. 根据 decision 组装输出
            answer_text, hint = self._apply_decision(answer, decision)
            coverage = decision.coverage.value

            # 6. 构造 sources
            sources = [
                RetrievalSource(
                    document_id=r.document_id,
                    chunk_id=r.chunk_id,
                    title=r.title,
                    source_url=r.source_url or None,
                    updated_at=datetime.fromtimestamp(r.updated_at, tz=timezone.utc),
                    score=r.score,
                    namespace=r.dept_namespace,
                )
                for r in results
            ]

            latency_ms = int((time.time() - start) * 1000)
            logger.info(f"KNOWLEDGE_COMPLETED latency_ms={latency_ms} tokens={tokens}")

            return AgentResult(
                agent_name="knowledge",
                success=True,
                confidence=combined_score,
                output={
                    "answer": answer_text,
                    "coverage": coverage,
                    "hint": hint,
                    "stage": stage,
                    "scene": scene,
                    "threshold_used": decision.threshold_used,
                    "decision_reason": decision.reason,
                },
                sources=sources,
                tokens_used=tokens,
                latency_ms=latency_ms,
                needs_replan=(coverage == Coverage.PARTIAL.value),
                replan_reason=(
                    "low_confidence_partial" if coverage == Coverage.PARTIAL.value else None
                ),
            )

        except Exception as e:  # noqa: BLE001
            from app.core.execution_budget import check_execution_budget
            check_execution_budget()
            logger.error("KNOWLEDGE_SERVICE_FAILED")
            return AgentResult(
                agent_name="knowledge",
                success=False,
                confidence=0.0,
                output={"answer": "知识检索服务异常，请稍后重试。", "coverage": "none"},
                sources=[],
                error="KNOWLEDGE_SERVICE_FAILED",
                latency_ms=int((time.time() - start) * 1000),
            )

    async def _generate_answer(
        self, query: str, results: list[SearchResult], history: Optional[list[dict]] = None
    ) -> tuple[str, Optional[float]]:
        """调用 LLM 生成答案 + 自评分数(async:P2-2 起 ainvoke，取消可在 LLM 等待期间生效)

        I-07:token 用量不再从响应 usage_metadata 逐点提取,改由统一 callback
        (TokenUsageCallbackHandler)采集,调用方读请求级累加器差值。
        """
        from langchain_core.messages import HumanMessage, SystemMessage
        from app.security.rag_boundary import (
            NO_ANSWER, answer_data, build_prompt, model_text, validate_answer,
        )

        if not results:
            return NO_ANSWER, None
        from app.rag.score_admission import check_result_scores
        check_result_scores(results)

        # 答案生成用 lite(flash):pro 是推理模型,95% token 消耗在隐藏推理上
        # (实测 RAG 答案 1694 token 中仅 ~5% 可见,耗时 60-90s);
        # RAG 答案有严格片段约束,flash 质量足够且快 3-4 倍
        tpl, pv = get_prompt("knowledge_rag_answer")
        prompt = build_prompt(tpl, pv, answer_data(query, results, history), {'context', 'query'})
        llm = get_lite_llm()
        answer_resp = await llm.ainvoke(
            [SystemMessage(content=prompt.system), HumanMessage(content=prompt.data)],
            config={"tags": ["rag_candidate"], "metadata": prompt.metadata},
        )
        answer_text = validate_answer(model_text(answer_resp), len(results))

        # LLM 自评(用本地小模型,免费高频;失败不影响主流程)
        # 条件化:检索分明显高(≥0.85,不过自评也稳过)或明显低(≤0.30,自评满分也救不回)
        # 时跳过,只在灰色区间评估——省一次本地模型调用(2-5s)
        llm_self_score: Optional[float] = None
        top_score = results[0].score if results else 0.0
        if top_score >= 0.85 or top_score <= 0.30:
            logger.debug(f"自评跳过： top_score={top_score:.3f} 在灰色区间外")
            return answer_text, None
        try:
            eval_llm = self._get_eval_llm()
            eval_tpl, _epv = get_prompt("knowledge_llm_self_eval")
            eval_prompt = build_prompt(eval_tpl, _epv, {'query': query, 'answer': answer_text[:500]},
                                       {'query', 'answer'})
            # num_predict 硬截断:qwen3.5 即使 reasoning=False 也可能啰嗦,
            # 自评只需 1-2 个数字,截断后生成 ~0.2s
            # (ChatOllama 用 model_copy 改 num_predict;primary 降级时回退 max_tokens)
            from langchain_ollama import ChatOllama

            if isinstance(eval_llm, ChatOllama):
                eval_llm = eval_llm.model_copy(update={"num_predict": 10})
            else:
                eval_llm = eval_llm.bind(max_tokens=10)
            eval_resp = await eval_llm.ainvoke(
                [SystemMessage(content=eval_prompt.system), HumanMessage(content=eval_prompt.data)],
                config={"tags": ["rag_evaluation"], "metadata": eval_prompt.metadata},
            )
            eval_text = model_text(eval_resp)
            # Coverage remains a heuristic; arbitrary digits in prose are not a score.
            if eval_text.strip() in {str(i) for i in range(11)}:
                llm_self_score = int(eval_text.strip()) / 10.0
        except Exception as e:  # noqa: BLE001
            from app.core.execution_budget import check_execution_budget
            check_execution_budget()
            logger.warning("KNOWLEDGE_SELF_EVALUATION_FAILED")

        return answer_text, llm_self_score

    @staticmethod
    def _apply_decision(answer: str, decision) -> tuple[str, Optional[str]]:
        """根据置信度决策组装最终答案 + 提示"""
        if decision.action == "reject":
            from app.security.rag_boundary import NO_ANSWER
            return NO_ANSWER, None
        if decision.action == "answer_with_hint":
            hint = (
                f"⚠️ 当前答案置信度较低({decision.score:.2f})，建议人工核实。"
                "如需更准确信息，请联系业务负责人。"
            )
            return answer, hint
        if decision.action == "answer_skip_hint":
            return answer, None
        # answer
        return answer, None
