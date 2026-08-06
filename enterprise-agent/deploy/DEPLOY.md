# 生产部署指南

> 适用：Hello，智多星——企业知识工作流 Agent v3
> 部署方式：Docker Compose（单机生产部署）
> 更新日期：2026-07-26

---

## 一、部署架构

```
                    ┌─────────────┐
   用户 ──HTTPS──→  │   Nginx     │  (80/443)
                    │  反代+TLS   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  API (×4)   │  uvicorn --workers 4
                    │  FastAPI    │
                    └──┬──┬──┬────┘
                       │  │  │
            ┌──────────┘  │  └──────────┐
            │             │             │
       ┌────▼────┐  ┌─────▼─────┐  ┌────▼────┐
       │ Milvus  │  │ PostgreSQL│  │  Redis  │
       │ 向量库  │  │  关系库   │  │  缓存   │
       └────┬────┘  └─────┬─────┘  └────┬────┘
            │             │             │
       ┌────▼────┐  ┌─────▼─────┐       │
       │  etcd   │  │  MinIO    │       │
       │ 元数据  │  │ 对象存储  │       │
       └─────────┘  └───────────┘       │
                                         │
                    ┌─────────────────────┘
                    │
              ┌─────▼─────┐
              │  Worker   │  后台任务
              └───────────┘
```

---

## 二、环境准备

### 2.1 服务器要求

| 资源 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 4 核 | 8 核 |
| 内存 | 16 GB | 32 GB |
| 磁盘 | 100 GB SSD | 500 GB SSD |
| 系统 | Linux (Ubuntu 22.04+) | Linux |

> 内存主要被 Milvus(4G) + API(4G) + Redis(2G) + MinIO(2G) + bge-m3 Embedding 模型(2G) 占用。

### 2.2 软件依赖

```bash
# Docker + Docker Compose
docker --version          # ≥ 24.0
docker compose version    # ≥ v2.20

# Git(拉取代码)
git --version
```

### 2.3 模型文件准备

将本地模型文件上传到服务器：

```bash
# 服务器创建目录
mkdir -p /data/models

# 上传(从开发机)
scp -r D:/models/bge-m3 user@server:/data/models/
scp -r D:/models/bge-reranker-large user@server:/data/models/

# 或用 HuggingFace 直接下载(服务器可联网时)
huggingface-cli download BAAI/bge-m3 --local-dir /data/models/bge-m3
huggingface-cli download BAAI/bge-reranker-large --local-dir /data/models/bge-reranker-large
```

---

## 三、配置文件

### 3.1 创建 `.env.prod`

```bash
cp .env .env.prod
```

编辑 `.env.prod`，**必须修改**以下字段：

```env
APP_ENV=prod

# 强密码(用 openssl rand -base64 32 生成)
POSTGRES_PASSWORD=<生成新密码>
REDIS_PASSWORD=<生成新密码>
JWT_SECRET_KEY=<生成新密码>
GRAFANA_ADMIN_PASSWORD=<生成新密码>

# DeepSeek API Key
OPENAI_API_KEY=<生产 Key>

# 模型路径(服务器路径)
EMBEDDING_MODEL=/data/models/bge-m3
RERANKER_MODEL=/data/models/bge-reranker-large

# Milvus 切换为真实后端
VECTOR_STORE_PROVIDER=milvus

# 关闭调试
LOG_LEVEL=INFO
```

### 3.2 生成强密码

```bash
openssl rand -base64 32
```

### 3.3 准备 SSL 证书

```bash
mkdir -p deploy/certs

# 方式 A:Let's Encrypt 免费证书(推荐,需域名)
certbot certonly --standalone -d api.your-domain.com
cp /etc/letsencrypt/live/api.your-domain.com/fullchain.pem deploy/certs/server.crt
cp /etc/letsencrypt/live/api.your-domain.com/privkey.pem deploy/certs/server.key

# 方式 B:自签名证书(仅内网测试)
openssl req -x509 -newkey rsa:4096 -nodes -days 365 \
  -keyout deploy/certs/server.key -out deploy/certs/server.crt \
  -subj "/CN=localhost"
```

### 3.4 创建备份目录

```bash
mkdir -p backups
```

---

## 四、部署步骤

### 4.1 拉取代码

```bash
git clone <repo-url> /opt/enterprise-agent
cd /opt/enterprise-agent
git checkout main
```

### 4.2 启动服务

```bash
# 启动核心服务(不含监控)
docker compose -f docker-compose.prod.yml up -d

# 启动监控(Prometheus + Grafana)
docker compose -f docker-compose.prod.yml --profile monitoring up -d
```

### 4.3 验证部署

```bash
# 1. 容器状态
docker compose -f docker-compose.prod.yml ps

# 2. 健康检查
curl -k https://localhost/health
# 期望: {"status":"healthy","version":"1.0.0"}

# 3. 就绪检查
curl -k https://localhost/ready
# 期望: db/milvus/checkpointer 全部 healthy

# 4. API 文档
curl -k https://localhost/docs
```

### 4.4 初始化知识库

```bash
# 入库样本文档
docker compose -f docker-compose.prod.yml exec api \
  python -m eval.run_eval --ingest --recreate
```

---

## 五、备份与恢复

### 5.1 自动备份脚本

备份脚本已入库：`scripts/backup.sh`（每日 pg_dump + etcd snapshot + MinIO/milvus 数据卷
整卷 tar，保留 7 天，产出 `backups/pg_<时间戳>.sql.gz`、`etcd_<时间戳>.db`、
`minio_<时间戳>.tar.gz`、`milvus_<时间戳>.tar.gz`，可用 `BACKUP_DIR` / `RETAIN_DAYS` /
`COMPOSE_FILES` / `COMPOSE_PROJECT` / `STOP_MILVUS` 环境变量覆盖默认值）：

```bash
scripts/backup.sh
```

> 备份覆盖说明（2026-08-05 首次恢复演练发现缺口、2026-08-06 补齐并复演验证，ISSUES I-12）：
> Milvus 可恢复 = etcd 元数据 + MinIO 对象（向量数据本体）+ milvus 本地卷（rocksmq）三件套，
> 缺一不可。整卷 tar 是运行中系统的近一致快照，需严格一致时设 `STOP_MILVUS=1`（短暂中断检索）。

### 5.2 配置定时任务

```bash
chmod +x scripts/backup.sh

# 添加 crontab
crontab -e

# 每日凌晨 2 点备份
0 2 * * * /opt/enterprise-agent/scripts/backup.sh >> /var/log/agent_backup.log 2>&1
```

### 5.3 恢复流程

> 以下步骤为 2026-08-05 首次恢复演练（ISSUES I-12）实测修正版；
> 演练用隔离环境可复用 `deploy/docker-compose.dr-drill.yml`（独立 project/端口/数据卷）。

```bash
# PostgreSQL 恢复(目标库已有 schema 时必须先清库,否则建表冲突)
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U agent enterprise_agent -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
gunzip < backups/pg_20260726_020000.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U agent enterprise_agent

# Milvus 恢复(停 Milvus → 停 etcd/minio → 清数据卷 → 恢复 etcd snapshot 与
#             MinIO/milvus 卷数据 → 启 etcd/minio → 启 Milvus)
# ⚠️ 在运行中的 etcd 上直接 snapshot restore 必失败(数据目录非空/被锁);
#    只恢复 etcd 元数据不恢复 MinIO/milvus 卷,集合会 load 挂起(实测,ISSUES I-12)
docker compose -f docker-compose.prod.yml stop milvus-standalone etcd minio
docker run --rm -v <project>_etcd_data:/etcd alpine sh -c 'rm -rf /etcd/* /etcd/.[!.]*'
docker run --rm -v <project>_etcd_data:/etcd -v "$(pwd)/backups:/b:ro" \
  quay.io/coreos/etcd:v3.5.5 \
  etcdctl snapshot restore /b/etcd_20260726_020000.db --data-dir /etcd
docker run --rm -v <project>_minio_data:/data -v "$(pwd)/backups:/b:ro" alpine \
  sh -c 'rm -rf /data/* /data/.[!.]* && tar xzf /b/minio_20260726_020000.tar.gz -C /data'
docker run --rm -v <project>_milvus_data:/data -v "$(pwd)/backups:/b:ro" alpine \
  sh -c 'rm -rf /data/* /data/.[!.]* && tar xzf /b/milvus_20260726_020000.tar.gz -C /data'
docker compose -f docker-compose.prod.yml up -d etcd minio milvus-standalone
```

> 恢复后一致性核查：`/ready` 全 healthy；PG 关键表行数与备份时点比对；
> Milvus 集合 `load` 后 `num_entities` 与备份时点比对（仅 `get_collection_stats`
> 的数字一致不算数——它读的是元数据，segment 缺失时 load 会挂起）。

---

## 六、监控

### 6.1 访问 Grafana

```bash
# 启动监控
docker compose -f docker-compose.prod.yml --profile monitoring up -d

# 访问
http://server-ip:3000
# 用户: admin / 密码: .env.prod 中的 GRAFANA_ADMIN_PASSWORD
```

### 6.2 关键指标

| 指标 | 来源 | 告警阈值 |
|------|------|---------|
| API 延迟 P95 | metrics_middleware | > 5s |
| 错误率 | metrics_middleware | > 5% |
| Milvus 内存 | /ready | > 80% |
| PostgreSQL 连接数 | pg_stat_activity | > 80 |
| Redis 内存 | redis-cli info memory | > 80% maxmemory |
| 磁盘使用率 | df -h | > 85% |

> 告警规则已落成 `deploy/prometheus-alerts.yml`（15 条：SLA 口径 warning / 运维口径 critical，
> 每条标注口径来源），由 Compose monitoring profile 挂载加载；配套的
> postgres-exporter / redis-exporter / node-exporter 已在 monitoring profile 中提供。
> 值班预案（告警分级/响应动作/升级路径）见 `docs/30-guides/运维维护手册.md` 第 10 章。

### 6.3 日志查看

```bash
# API 日志
docker compose -f docker-compose.prod.yml logs -f api

# 特定时间段
docker compose -f docker-compose.prod.yml logs --since 1h api

# Nginx 访问日志
docker compose -f docker-compose.prod.yml exec nginx cat /var/log/nginx/access.log
```

---

## 七、运维操作

### 7.1 滚动更新

```bash
# 拉取新代码
git pull origin main

# 重新构建 API 镜像
docker compose -f docker-compose.prod.yml build api worker

# 滚动重启(无停机,Nginx 会自动重试)
docker compose -f docker-compose.prod.yml up -d --no-deps api worker
```

### 7.2 扩容（多实例）

单机内扩容（增加 worker 数）：

```bash
docker compose -f docker-compose.prod.yml up -d --scale api=2
```

> 多机部署需要额外引入负载均衡器（HAProxy/Nginx）+ 共享存储（NFS/S3），届时再评估是否上 K8s。

### 7.3 限流调整

修改 `deploy/nginx.conf`：

```nginx
# 全局 IP 限流
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/s;

# 单接口限流(在 location 内)
limit_req zone=api_limit burst=60 nodelay;
```

### 7.4 清理

```bash
# 停止全部服务(保留数据)
docker compose -f docker-compose.prod.yml down

# 停止并删除数据卷(⚠️ 危险,会丢失全部数据)
docker compose -f docker-compose.prod.yml down -v

# 清理无用镜像
docker image prune -f
```

---

## 八、安全清单

- [x] 所有密码用 `openssl rand -base64 32` 生成
- [x] `.env.prod` 权限设为 `chmod 600 .env.prod`
- [x] HTTPS 强制（HTTP 自动跳转）
- [x] 安全响应头（HSTS / X-Frame-Options 等）
- [x] Nginx 限流（30r/s + burst 60）
- [x] API 限流（rate_limit_middleware，Redis 优先）
- [x] JWT 自动刷新（/api/v1/auth/refresh）
- [x] RBAC 工具权限校验（5 角色 × 8 工具）
- [x] Prompt 注入检测（9 种模式）
- [ ] 防火墙仅开放 80/443 端口（`ufw allow 80,443/tcp`）
- [ ] 定期更新基础镜像（`docker compose pull && docker compose up -d`）

---

## 九、故障排查

### 9.1 API 起不来

```bash
# 查看启动日志
docker compose -f docker-compose.prod.yml logs api | tail -50

# 常见原因:
# - .env.prod 缺少必填字段(POSTGRES_PASSWORD 等)
# - Milvus/PG/Redis 未就绪(depends_on healthy 检查)
# - 模型路径错误(EMBEDDING_MODEL 不存在)
```

### 9.2 Milvus 检索返回 0 条

```bash
# 检查集合状态
docker compose -f docker-compose.prod.yml exec api \
  python -c "from app.core.milvus_client import get_collection; c = get_collection(); print(c.num_entities)"

# 检查命名空间过滤
# 用户 dept_sales 可访问:本部门文档 + shared_company
```

### 9.3 Redis Checkpointer 失效

```bash
# 检查 RediSearch 模块
docker compose -f docker-compose.prod.yml exec redis redis-cli -a $REDIS_PASSWORD MODULE LIST

# 应包含: search + ReJSON
# 不包含则自动降级 PostgreSQL(三级降级链)
```

### 9.4 磁盘满

```bash
# 查看磁盘占用
docker system df

# 清理日志(json-file 日志会占空间)
docker compose -f docker-compose.prod.yml logs --tail 0 -f api  # 看实时
# 然后 truncate 旧日志
find /var/lib/docker/containers -name "*.log" -mtime +7 -delete
```

---

## 十、什么时候该上 K8s

当前单机 Compose 部署在以下条件**全部满足**前都不需要 K8s：

- 日活用户 < 1 万
- 单机 32G 内存够用
- 无多环境隔离需求（dev/staging/prod）
- 团队无专职 DevOps

**触发上 K8s 的信号**：
1. 单机 CPU/内存长期 > 80%
2. 需要 99.9%+ SLA（多副本 + 自动故障转移）
3. 有多环境部署需求
4. 服务实例 > 10 个，Compose 管理变复杂

届时可参考 v3 方案附录的 K8s 清单，但**当前阶段 Compose 已足够**。
