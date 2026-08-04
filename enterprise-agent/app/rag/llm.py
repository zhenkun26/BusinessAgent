"""LLM 工厂(支持 DeepSeek / OpenAI / 智谱 / 通义 / Ollama 等 OpenAI 兼容协议)

模型路由策略:
- primary: 复杂任务(任务分解/多结果汇总/分析报告)→ DeepSeek 云端 v4-pro
- lite: 轻量任务(意图分类/工具选择/计划解析/grounded 答案生成)→ 本地 Ollama qwen3.5:4b 优先,降级 DeepSeek v4-flash
- local: 本地高频简单任务(闲聊判断/答案自评/Reranker 评分)+ 云端兜底(Ollama qwen3.5:4b)

降级策略(初始化时判定一次,非运行时逐层切换):
- primary: 云端(配置了 OPENAI_API_KEY)→ 本地 Ollama(无 key 时)
- lite: 本地 Ollama → 云端 v4-flash → primary 兜底
- 运行时单次调用失败由 ChatOpenAI max_retries 重试;仍失败则各调用点
  走非 LLM 兜底(规则匹配/关键词映射/表格直出/直接拼接)

设计要点:
- 大模型用于需要推理/理解的关键任务(任务分解、多结果汇总、分析报告)
- 小模型用于高频轻量任务(分类、抽取、自评、Reranker 评分)
- 本地模型承担免费的简单任务,同时作为云端不可用时的兜底
"""

from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from loguru import logger

from app.config import get_settings


class LLMRouter:
    """LLM 路由器(按任务复杂度选模型)"""

    def __init__(self):
        self._settings = get_settings()
        self._primary: Optional[BaseChatModel] = None
        self._lite: Optional[BaseChatModel] = None
        self._local: Optional[BaseChatModel] = None
        self._cloud_lite: Optional[BaseChatModel] = None

    def get_primary(self) -> BaseChatModel:
        """主模型(复杂任务:答案生成/规划/报告)

        优先级:
        1. DeepSeek 云端(配置了 OPENAI_API_KEY 时)
        2. 本地 Ollama(无 key 时降级,保证开发期可用)
        """
        if self._primary is None:
            s = self._settings
            if s.openai_api_key:
                # 云端 DeepSeek
                self._primary = ChatOpenAI(
                    model=s.primary_llm_model,
                    api_key=s.openai_api_key,
                    base_url=s.openai_base_url,
                    temperature=s.primary_llm_temperature,
                    max_tokens=s.primary_llm_max_tokens,
                    timeout=60,
                    max_retries=2,
                    streaming=True,  # 支持 astream_events 的 token 级流式输出(行为不变)
                )
                logger.info(f"主 LLM(云端): {s.openai_base_url} / {s.primary_llm_model}")
            else:
                # 无 key,降级本地 Ollama
                logger.warning(
                    "OPENAI_API_KEY 未配置,主 LLM 降级使用本地 Ollama "
                    f"({s.local_llm_model})。答案生成质量会受限,建议配置 DeepSeek key。"
                )
                self._primary = self._get_local_chat_model(
                    temperature=s.primary_llm_temperature,
                    max_tokens=s.primary_llm_max_tokens,
                    timeout=120,
                    streaming=True,  # 支持 token 级流式
                )
        return self._primary

    def get_lite(self) -> BaseChatModel:
        """轻量模型(意图分类/工具选择/计划解析/grounded 答案生成)

        优先级:
        1. 本地 Ollama(qwen3.5:4b,ChatOllama+reasoning=False 后实测 0.2-1.4s,
           免费且快于云端 flash 的 8.7-18.1s)
        2. 云端 lite 模型(DeepSeek v4-flash,本地不可用时降级)
        3. primary(云端也未配置时兜底)
        """
        if self._lite is None:
            s = self._settings
            # 1. 优先本地 Ollama(validate_model_on_init 在初始化时探测连通性,
            #    Ollama 未启动/模型不存在会抛异常,落入下一级)
            try:
                self._lite = self._get_local_chat_model(
                    temperature=0.1,
                    max_tokens=1024,
                    timeout=30,
                )
                logger.info(
                    f"轻量 LLM(本地): {s.local_llm_base_url} / {s.local_llm_model}"
                )
                return self._lite
            except Exception as e:  # noqa: BLE001
                logger.warning(f"本地 Ollama 不可用,轻量 LLM 降级云端: {e}")

            # 2. 降级云端轻量模型(如 deepseek-v4-flash)
            cloud = self.get_cloud_lite()
            if cloud is not None:
                self._lite = cloud
                return self._lite

            # 3. 云端也未配置,兜底 primary
            logger.warning("本地/云端轻量 LLM 均不可用,轻量 LLM 降级使用 primary")
            self._lite = self.get_primary()
        return self._lite

    def get_cloud_lite(self) -> Optional[BaseChatModel]:
        """云端轻量模型(DeepSeek v4-flash);未配置 key 时返回 None

        用途:① lite 链路的云端降级;② 本地小模型质量不足时的按需回退
        (如 ExecutionAgent 工具选择:本地返回空 → 云端重试一次)。
        """
        if self._cloud_lite is None:
            s = self._settings
            if not (s.openai_api_key and s.lite_llm_model):
                return None
            try:
                self._cloud_lite = ChatOpenAI(
                    model=s.lite_llm_model,
                    api_key=s.openai_api_key,
                    base_url=s.openai_base_url,
                    temperature=0.1,
                    max_tokens=1024,
                    timeout=30,
                    max_retries=2,
                    streaming=True,  # 支持 token 级流式(knowledge 答案生成用 lite)
                    # 关闭思考模式(实测:默认 210 token 推理/3.9s → 关闭后 0 推理/1.4s;
                    # 分类/选择/grounded 答案均不需要推理;等效已下架的 deepseek-chat)
                    extra_body={"thinking": {"type": "disabled"}},
                )
                logger.info(
                    f"云端轻量 LLM: {s.openai_base_url} / {s.lite_llm_model}"
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"云端轻量 LLM 初始化失败: {e}")
                return None
        return self._cloud_lite

    def get_local(self) -> Optional[BaseChatModel]:
        """本地模型(Ollama qwen3.5:4b,闲聊判断/答案自评/Reranker 评分 + 云端兜底)"""
        if self._local is None:
            self._local = self._get_local_chat_model(
                temperature=0.2,
                max_tokens=1024,
                timeout=120,
            )
        return self._local

    def _get_local_chat_model(
        self,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        timeout: int = 60,
        streaming: bool = False,
    ) -> BaseChatModel:
        """构造本地 Ollama ChatOllama 客户端

        为什么用 ChatOllama 而不是 ChatOpenAI 指 Ollama 的 /v1 端点:
        Ollama 的 OpenAI 兼容端点会忽略 extra_body={"think": False},
        模型照样生成 thinking token(实测自评单次 44-94s);
        ChatOllama + reasoning=False 走原生 /api/chat,真正关闭思考,
        实测意图分类 0.2s / 知识问答 1.4s / 工具选择 0.2s。

        validate_model_on_init=True:初始化即探测 Ollama 连通性与模型存在性,
        让 get_lite/get_local 的 try/except 降级在 Ollama 未启动时真实生效。
        """
        from langchain_ollama import ChatOllama

        s = self._settings
        # ChatOllama 的 base_url 不带 /v1 后缀(配置项兼容 OpenAI 风格,这里剥掉)
        base_url = s.local_llm_base_url.rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[: -len("/v1")]
        # trust_env=False:绕过系统代理(本机实测代理把 localhost 请求
        # 转给代理服务器,叠加 SDK 重试,单次调用 45-66s;直连 1-3s)
        return ChatOllama(
            model=s.local_llm_model,
            base_url=base_url,
            temperature=temperature,
            num_predict=max_tokens,
            reasoning=False,
            validate_model_on_init=True,
            sync_client_kwargs={"trust_env": False, "timeout": timeout},
            async_client_kwargs={"trust_env": False, "timeout": timeout},
        )


# 全局单例
_router: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


def get_primary_llm() -> BaseChatModel:
    """快捷入口:主 LLM(答案生成/规划)"""
    return get_llm_router().get_primary()


def get_lite_llm() -> BaseChatModel:
    """快捷入口:轻量 LLM(意图分类/评分/Reranker)"""
    return get_llm_router().get_lite()


def get_cloud_lite_llm() -> Optional[BaseChatModel]:
    """快捷入口:云端轻量 LLM(本地质量不足时的按需回退;未配置 key 返回 None)"""
    return get_llm_router().get_cloud_lite()


def get_local_llm() -> BaseChatModel:
    """快捷入口:本地降级 LLM"""
    return get_llm_router().get_local()
