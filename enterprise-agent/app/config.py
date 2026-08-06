"""配置管理 - 集中式环境变量加载"""

from functools import lru_cache
from typing import Optional

from loguru import logger
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

    # ---- 认证与安全(生产加固) ----
    # 开启后登录必须校验 bcrypt 密码(演示环境保持 False 兼容"密码任意")
    auth_require_password: bool = False
    # 开启后每个受保护请求回查 users 表(禁用用户/角色变更即时生效;DB 故障降级 JWT)
    auth_check_db: bool = True
    # CORS 白名单(逗号分隔);dev 默认本机来源;生产禁止通配+credentials
    cors_allow_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

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
    # 外部业务系统凭证(仅环境变量注入;空值时 http 适配器返回 401 语义错误)
    crm_api_token: str = ""
    mail_api_token: str = ""
    ticket_api_token: str = ""
    # 工具提供方: mock(默认,进程内数据)/ http(真实业务系统适配)
    tool_provider: str = "mock"
    # 外部 HTTP 调用超时与重试(mock 提供方不生效)
    external_timeout_seconds: float = 10.0
    external_max_retries: int = 2

    # ---- 限流 ----
    rate_limit_per_minute: int = 60

    # ---- Checkpoint 滑动过期(I-06) ----
    # Redis checkpointer 的 thread 键 TTL(天);每次会话活跃(写入/读取)滑动刷新。
    # <=0 表示不设 TTL(恢复旧行为);仅 Redis 主路径生效,PG/Memory 降级后端不设。
    checkpoint_ttl_days: int = 7

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


# 生产环境必须覆盖的默认凭证(防止"默认值上线"事故)
_DEFAULT_SECRETS: dict[str, str] = {
    "jwt_secret_key": "change-me-in-production",
    "postgres_password": "wJ6pbV5eBkzMT2AYDT9w2i8V",
    "redis_password": "V5lOkygYvgaD6ZZ8rmqJAcO7",
    "milvus_password": "Milvus123",
}


def validate_production_settings(settings: Optional[Settings] = None) -> list[str]:
    """生产模式配置强校验(启动时调用)

    检查 JWT 密钥与数据库口令是否为代码默认值。生产环境使用默认凭证
    意味着任何知情者都能伪造 token 或直连数据库——必须显式覆盖。

    Args:
        settings: 配置实例;None 时使用全局单例

    Returns:
        违反项列表;为空表示通过
    """
    settings = settings or get_settings()
    if settings.is_dev:
        return []

    violations: list[str] = []
    for field_name, default_value in _DEFAULT_SECRETS.items():
        actual = getattr(settings, field_name)
        if actual == default_value:
            violations.append(
                f"{field_name} 仍为代码默认值({default_value[:6]}...),"
                f"生产环境必须通过环境变量覆盖"
            )
    if not settings.jwt_secret_key or len(settings.jwt_secret_key) < 32:
        violations.append("jwt_secret_key 长度必须 >= 32(使用 openssl rand -base64 32 生成)")
    if settings.cors_allow_origins.strip() == "*":
        violations.append("生产环境禁止 CORS 通配来源(cors_allow_origins='*')")
    return violations


@lru_cache
def get_settings() -> Settings:
    return Settings()
