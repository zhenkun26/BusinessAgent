FROM python:3.11-slim

WORKDIR /app

# 系统依赖(build-essential 编译 torch/sentence-transformers C 扩展)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖(利用 Docker 层缓存)
COPY pyproject.toml ./
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -e ".[dev]"

# 预下载 bge-m3 模型到镜像(避免每次容器启动重新下载 2.3GB)
# 模型缓存到 /data/hf_cache,运行时通过 HF_HOME 环境变量复用
RUN mkdir -p /data/hf_cache && \
    HF_HOME=/data/hf_cache \
    SENTENCE_TRANSFORMERS_HOME=/data/hf_cache \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')" || \
    echo "WARN: 模型预下载失败,容器启动时会重试"

# 应用代码
COPY app ./app
COPY eval ./eval
COPY deploy ./deploy

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
