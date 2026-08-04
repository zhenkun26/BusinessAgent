#!/bin/bash
# ============================================
# Hello，小A——macOS 一键启动脚本
# 对应 Windows 版 启动小A.bat
# 功能:自检 Docker → 启动基础设施(PG/Redis,可选 Milvus)→ 启动 API → 打开 /ui
# 用法:双击本文件(首次需在 系统设置→隐私与安全性 允许运行)
# ============================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$PROJECT_DIR/enterprise-agent"
VENV_PY="$API_DIR/.venv/bin/python"
PORT=8000

echo "== Hello，小A macOS 启动器 =="

# 1. Docker 自检(未运行则启动 Docker Desktop 并等待)
if ! docker info >/dev/null 2>&1; then
  echo "== Docker 未运行,启动 Docker Desktop… =="
  open -a Docker
  for i in $(seq 1 60); do
    if docker info >/dev/null 2>&1; then
      echo "== Docker 已就绪 =="
      break
    fi
    sleep 2
  done
  docker info >/dev/null 2>&1 || { echo "!! Docker 启动超时,请手动打开 Docker Desktop"; exit 1; }
fi

# 2. 基础设施:PG + Redis(必需);Milvus 可选(首次拉镜像较慢,注释掉则跳过)
cd "$API_DIR"
echo "== 启动 PostgreSQL + Redis =="

# 6379 端口冲突自检:本机若有原生 Redis(如 brew 服务)占用 localhost:6379,
# 会遮蔽 Docker Redis 导致认证失败/限流降级。提示用户停止后重试。
if lsof -iTCP:6379 -sTCP:LISTEN -P 2>/dev/null | grep -v 'com.docke' | grep -q 'redis'; then
  echo "!! 检测到非 Docker 的 Redis 占用 6379 端口(常见为 Homebrew 服务)。"
  echo "   请先执行: brew services stop redis"
  echo "   再重新运行本脚本。(恢复: brew services start redis)"
  exit 1
fi

docker compose up -d postgres redis

# 向量检索(Milvus + etcd + MinIO;首次会拉取约 2.5GB 镜像)
docker compose up -d etcd minio milvus-standalone

# 3. 数据库初始化(幂等:已有表/数据会自动跳过)
echo "== 初始化数据库(幂等) =="
docker exec -i enterprise-agent-postgres-1 psql -U agent enterprise_agent < deploy/init.sql
docker exec -i enterprise-agent-postgres-1 psql -U agent enterprise_agent < deploy/migrations/001_prompt_versions.sql
docker exec -i enterprise-agent-postgres-1 psql -U agent enterprise_agent < deploy/migrations/002_documents_ledger.sql

# 4. Python 环境(.venv 缺失时用 uv 创建并安装启动依赖)
if [ ! -x "$VENV_PY" ]; then
  echo "== 首次运行:创建虚拟环境并安装依赖 =="
  command -v uv >/dev/null 2>&1 || { echo "!! 缺少 uv,请先安装: brew install uv"; exit 1; }
  uv venv "$API_DIR/.venv" --python 3.13
  uv pip install --python "$VENV_PY" \
    fastapi 'uvicorn[standard]' python-multipart 'sqlalchemy>=2.0' asyncpg redis \
    pydantic pydantic-settings loguru PyJWT 'passlib[bcrypt]' python-dotenv httpx \
    tenacity langchain-core langchain-openai langchain-ollama langchain-text-splitters \
    'langgraph>=1.2' langgraph-checkpoint-redis langgraph-checkpoint-postgres langsmith \
    'pymilvus>=2.4,<3.1' numpy greenlet prometheus-client opentelemetry-api \
    opentelemetry-sdk opentelemetry-instrumentation-fastapi pypdf python-docx circuitbreaker
fi

# 5. 启动 API(如已在运行则跳过)
if curl -s -o /dev/null "http://localhost:$PORT/health"; then
  echo "== API 已在运行: http://localhost:$PORT/ui =="
else
  echo "== 启动 API(日志见下方,关闭窗口即停止) =="
  (
    cd "$API_DIR"
    PYTHONIOENCODING=utf-8 "$VENV_PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
  ) &
  for i in $(seq 1 30); do
    if curl -s -o /dev/null "http://localhost:$PORT/health"; then
      break
    fi
    sleep 1
  done
  curl -s -o /dev/null "http://localhost:$PORT/health" || { echo "!! API 启动失败,请查看上方日志"; exit 1; }
fi

# 5.1 启动 Worker(审批超时扫描/任务队列/审计回写;已运行则跳过)
if pgrep -f "app.worker" >/dev/null 2>&1; then
  echo "== Worker 已在运行 =="
else
  echo "== 启动 Worker(后台任务) =="
  (
    cd "$API_DIR"
    nohup env PYTHONIOENCODING=utf-8 "$VENV_PY" -m app.worker > "$API_DIR/logs/worker.log" 2>&1 &
  )
fi

# 6. 打开页面
echo "== 打开 http://localhost:$PORT/ui =="
open "http://localhost:$PORT/ui"
