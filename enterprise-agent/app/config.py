"""配置管理 - 集中式环境变量加载"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置(从 .env 加载)"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- 应用 ----
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # ---- LLM(主) ----
    # 兼容 OpenAI 协议(DeepSeek / 智谱 GLM / 通义 / 百炼 等只需改 base_url + model + key)
    llm_provider: str = "openai_compatible"  # openai_compatible | local
    openai_api_key: str = ""
    openai_base_url: str = "https://api.deepseek.com/v1"  # DeepSeek 默认
    primary_llm_model: str = "deepseek-v4-pro"  # 复杂任务:规划/策略/报告
    lite_llm_model: str = "deepseek-v4-flash"  # 轻量任务:意图分类/简单问答
    primary_llm_temperature: float = 0.2
    primary_llm_max_tokens: int = 2048  # 推理模型大部分 token 消耗在隐藏推理上,调低会截断答案,勿轻易改小

    # ---- LLM(本地降级:Ollama) ----
    local_llm_base_url: str = "http://localhost:11434/v1"  # Ollama 默认端口
    local_llm_model: str = "qwen3.5:4b"
    local_llm_api_key: str = "EMPTY"

    # ---- Embedding(默认本地 bge-m3,1024 维) ----
    # EMBEDDING_MODEL 支持 HuggingFace repo id(自动下载)或本地路径(如 D:/models/bge-m3)
    embedding_provider: str = "local"  # openai | local
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    # 本地 embedding/reranker 运行设备:auto(自动) | cuda | cpu
    # 模拟生产/显存紧张时设 cpu,把 GPU 让给 Ollama LLM(实测:12G 卡上
    # bge 两模型占 ~5G,会把 qwen 挤到 CPU 计算,单次 3s→50s 波动)
    local_model_device: str = "auto"
    # 本地模型缓存目录(容器内挂 volume,宿主机开发由 .env 指向实际路径)
    hf_home: str = "/data/hf_cache"

    # ---- VectorStore 后端 ----
    # milvus: 生产用(需 Docker);memory: 开发期 Mock(InMemoryVectorStore,无需 Docker)
    vector_store_provider: str = "milvus"

    # ---- Milvus ----
    # 默认 localhost(宿主机开发);容器内由 docker-compose environment 覆盖为服务名
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection: str = "enterprise_knowledge"
    milvus_user: str = "root"
    milvus_password: str = "Milvus123"

    # ---- PostgreSQL ----
    # 密码与 docker-compose.yml 开发默认值一致(生产经 .env.prod 覆盖)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "agent"
    postgres_password: str = "wJ6pbV5eBkzMT2AYDT9w2i8V"
    postgres_db: str = "enterprise_agent"

    # ---- Redis ----
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = "V5lOkygYvgaD6ZZ8rmqJAcO7"  # 与 docker-compose requirepass 一致
    redis_db: int = 0

    # ---- JWT ----
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 480

    # ---- Cohere Reranker(可选,留空时用 LLM 距离排序降级) ----
    cohere_api_key: str = ""
    cohere_rerank_model: str = "rerank-multilingual-v3.0"

    # ---- Reranker 后端选择 ----
    # local_bge: 本地 bge-reranker-large(免费,推荐);cohere;llm;passthrough
    # RERANKER_MODEL 支持 HuggingFace repo id(自动下载)或本地路径(如 D:/models/bge-reranker-large)
    reranker_provider: str = "local_bge"
    reranker_model: str = "BAAI/bge-reranker-large"

    # ---- 业务系统 ----
    crm_api_base: str = "https://crm.internal/api/v1"
    mail_api_base: str = "https://mail.internal/api/v1"
    ticket_api_base: str = "https://ticket.internal/api/v1"

    # ---- 限流 ----
    rate_limit_per_minute: int = 60

    # ---- 知识库反馈循环 ----
    # dislike 反馈带 comment 时,自动生成知识候选(documents draft)供运营审核
    kb_feedback_auto_draft: bool = True

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def milvus_uri(self) -> str:
        return f"http://{self.milvus_host}:{self.milvus_port}"

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
