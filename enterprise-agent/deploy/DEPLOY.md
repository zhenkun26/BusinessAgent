# 生产部署指南

> 适用：智多星 v1.3.0；候选提交与镜像摘要必须另行记录。
> 部署方式：Linux 单机 Docker Compose；工程候选配置，不代表已完成生产验收。当前版本、schema、提交与证据关系见[交付状态](../../docs/50-engineering/delivery-status.md)。
> 更新日期：2026-10-17（C01 配置、C02/C03 离线增量已实现；真实 API/PostgreSQL/Linux 验收 BLOCKED）
>
> C01 已统一镜像引用和访问入口；模型 profile、数据库初始化、多进程状态分别由 C02/C03/C09 验收。当前不能仅凭本指南宣称完整系统可交付。当前 C22 已提供保留式恢复候选，真实运行及 D01–D16 验收仍 BLOCKED；历史演练不能替代当前结果。

---

## 一、部署架构

```
                    ┌─────────────┐
   用户 ──HTTPS──→  │   Nginx     │  (80/443)
                    │  反代+TLS   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  API (×1)   │  uvicorn --workers 1
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

> 上表为历史参考，不是当前模型 profile 的实测下限。C02 外部模型候选为单 API 进程与独立 worker，各 2 GiB 预算，不再加载本地 BGE 权重；数据库等基础设施仍需独立资源。实际容量、峰值与时延尚未测量，见 [模型 profile](MODEL_PROFILE.md)。

### 2.2 软件依赖

```bash
# Docker + Docker Compose
docker --version          # ≥ 24.0
docker compose version    # ≥ v2.20

# Git(拉取代码)
git --version
```

### 2.3 模型文件准备

生产候选为 `bailian-deepseek-v1`：百炼北京向量与重排、DeepSeek Flash 默认与 Pro 复杂任务。账号、独立密钥、接口、计费与验收边界见 [MODEL_PROFILE.md](MODEL_PROFILE.md)。无需准备本地模型快照；保留旧卷与 BGE 集合。新向量必须写入独立集合，本轮不执行索引或迁移。

生产候选不加载本地权重；凭证、模型配置或付费探针授权未就绪时拒绝启动。

---

## 三、配置文件

### 3.1 创建 `.env.prod`

在 `enterprise-agent/` 下创建私有 `.env.prod`；已有文件只编辑需要的字段，不覆盖现有配置。参考 `.env.example` 补齐应用配置。`env_file: .env.prod` 只负责容器环境；Compose 的镜像、密码等 `${...}` 插值通过下文每条命令的 `--env-file .env.prod` 显式读取。不要把真实配置或 `docker compose config` 全文放入聊天、日志或 Git。

编辑 `.env.prod`，**必须修改**以下字段：

```env
APP_ENV=prod
AUTH_REQUIRE_PASSWORD=true

# 必须取自经审查的 CI 候选及镜像仓库，不使用 latest 或可变 tag
BUSINESSAGENT_IMAGE=ghcr.io/<owner>/businessagent@sha256:<64位实际摘要>

# 强密码(用 openssl rand -base64 32 生成)
POSTGRES_PASSWORD=<生成新密码>
REDIS_PASSWORD=<生成新密码>
JWT_SECRET_KEY=<生成新密码>
GRAFANA_ADMIN_PASSWORD=<生成新密码>

# DeepSeek API Key
OPENAI_API_KEY=<生产 Key>

# Selected external model profile; keep probes disabled pending authorization.
MODEL_PROFILE=bailian-deepseek-v1
MODEL_STARTUP_PROBES_ENABLED=false
EMBEDDING_PROVIDER=bailian
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIM=1024
EMBEDDING_API_KEY=<private-beijing-key>
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
RERANKER_PROVIDER=bailian
RERANKER_MODEL=qwen3-rerank
RERANKER_API_KEY=<private-beijing-key>
RERANKER_BASE_URL=https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank
OPENAI_BASE_URL=https://api.deepseek.com/v1
LITE_LLM_MODEL=deepseek-flash
PRIMARY_LLM_MODEL=deepseek-v4-pro
MILVUS_COLLECTION=enterprise_knowledge_bailian_v4_1024_v1

# Milvus 切换为真实后端
VECTOR_STORE_PROVIDER=milvus

# 与实际 HTTPS 入口一致；生产不能使用通配来源
CORS_ALLOW_ORIGINS=https://<实际域名>

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
git clone <repo-url> /opt/BusinessAgent
cd /opt/BusinessAgent
git checkout <已审查的候选提交>
cd enterprise-agent
```

以下命令全部从 `enterprise-agent/` 执行。隔离验收时使用独立主机、端口和数据卷，不能覆盖已有实例。CI 使用 `Dockerfile.prod` 构建、扫描并按既有发布授权流程提供镜像；本 Compose **没有 build 路径**，API/worker 都使用 `.env.prod` 中的同一摘要。

### 4.2 验证配置与启动条件

C02 已实现外部模型方案与获批的 `libpq5` 配方；真实 API 与 Linux 构建/运行验收仍 BLOCKED，见 [模型 profile](MODEL_PROFILE.md)。以下命令未执行，需后续单独授权。生产默认因未授权付费探针而拒绝启动；获准后设置 `MODEL_STARTUP_PROBES_ENABLED=true`，每进程执行 5 次合成模型调用，重试与重启会增加费用。

```bash
# bash/zsh 中保留管道上游失败；只输出安全摘要，不打印渲染后的密码
set -o pipefail
docker compose --env-file .env.prod -f docker-compose.prod.yml config --format json \
  | python3 -I -B scripts/check_deployment_contract.py

# 只有契约检查 PASS 且允许启动隔离实例后，才拉取候选：
docker compose --env-file .env.prod -f docker-compose.prod.yml pull api worker
# 先按 DATABASE_BOOTSTRAP.md 启动 PostgreSQL、显式迁移/status/admin；逐步检查退出码。
# 数据库验收通过且 C02 付费探针另获授权后，才启动完整服务：
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --no-build

# 监控可选；指标走 Compose 网络中的 api:8000/metrics
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile monitoring up -d --no-build
```

契约检查失败必须停止，不继续执行启动行；它拒绝可变 tag、API/worker 不同镜像、应用 build、源码覆盖、宿主端口和 worker 误用 API 探针，但**不验证镜像是否存在、模型是否可用或业务启动成功**。缺失 Docker/Nginx 的环境不能执行后续验收。现有镜像构建与应用路径还需按 C24 的副作用规则复审；本次没有执行含删除的构建/清理命令。

C03 已移除两套 Compose 的自动 SQL 初始化挂载。空库必须使用同一候选镜像的显式迁移入口；旧库只能在获准的隔离副本上显式接管，不能直接运行历史 SQL 或对当前库迁移。管理员、演示种子、版本漂移及恢复步骤见 [数据库初始化手册](DATABASE_BOOTSTRAP.md)。默认没有账户或通用口令；真实 PostgreSQL 执行与登录仍 BLOCKED。

### 4.3 验证部署

```bash
# 1. 容器状态（running 不等于可用）
docker compose --env-file .env.prod -f docker-compose.prod.yml ps

# 2. 核对 Nginx 实际配置可加载；只检查，不 reload/清理
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T nginx nginx -t

# 3. 以下 -k 仅用于隔离环境自签证书；真实证书应删除 -k
curl -k -I https://localhost/
# 期望：302，Location: /ui/
curl -k -I https://localhost/ui/
# 期望：200，HTML；随后必须在浏览器完成实际登录
curl -k https://localhost/health
# 期望：healthy，version 与候选应用版本一致

# 4. 就绪检查：不能仅看 HTTP 200，C21 候选必需依赖失败返回 503；实际 O01–O16 验收仍 BLOCKED
curl -k https://localhost/ready
# 核对 components 下 db/redis/milvus/checkpointer/tools/workers/audit；全部 healthy 才是 200，否则 503

# 5. 文档与 schema
curl -k https://localhost/docs
curl -k https://localhost/openapi.json

# 6. 外部指标入口关闭，内部 Prometheus 采集单独核对
curl -k -o /dev/null -w '%{http_code}\n' https://localhost/metrics
# 期望：404

# 7. 只输出应用容器 ID 和实际 image ID，不打印环境变量
docker compose --env-file .env.prod -f docker-compose.prod.yml ps -q api worker \
  | xargs docker inspect --format '{{.Id}} {{.Image}}'
```

API 与 worker 的实际 image ID 必须一致，并与审查记录中的 registry digest 对应的本地镜像 ID 相同。部署记录保存候选提交、构建/扫描 run、registry digest、平台、API/worker image ID 与配置文件哈希；`docker image inspect <实际摘要引用> --format '{{.Id}}'` 可只读获得比对值。

浏览器人工验收仍必需：从 HTTPS 根路径进入 UI，完成授权测试账户登录，发起一条已批准的无副作用知识问答；开发者工具确认 `/api/v1/chat/stream` 返回事件流，观察增量事件而非结束后一次性出现；确认文档页成功加载 schema。记录实际角色、环境、首事件时间、结束状态与来源，不在截图中显示凭证。本机缺少目标运行环境，这些步骤尚未执行。

worker 使用同一应用镜像运行 `python -m app.worker`，C21 候选新增内部 8001 的 `/health`、`/ready`、`/metrics`，容器探针只调用自己的 `/ready`。API/worker 的必需依赖失败返回 503；API 会观察共享的两类消费者，worker 只观察自己的 UUID（75 秒窗口），不替代 admin 进度查询的 45 秒 fresh 指示。当前候选要求显式迁移 v8（包含 C21 v7）；迁移前排空并停止旧 API 写入进程，禁止新旧版本混跑，见 [C10 升级边界](../../docs/50-engineering/checkpoint-durability.md)，并共享 `audit_state` 保留式审计卷。真实就绪/持久化/告警验收仍 BLOCKED；双 API 独立采集与受控接收配方见 [C21 契约](../../docs/50-engineering/runtime-observability.md)，队列规则见[队列契约](../../docs/50-engineering/queue-reliability.md)。旧 Redis List 不搬迁或删除。

### 4.4 知识数据与镜像内容边界

生产镜像只包含应用及部署 schema/迁移，不包含宿主 `eval/`、`tests/` 或脚本；因此不能在 API 容器内运行 `python -m eval.run_eval`。知识初始化应使用明确授权的应用上传/发布流程，生命周期一致性由 C15 验收。不要用 `--recreate` 补救，避免触及既有集合。

---

## 五、备份与恢复

### 5.1 当前 C22 候选入口

当前使用 [保留式备份恢复契约](../../docs/50-engineering/retained-recovery.md)及
`scripts/recovery.py`。`backup.sh` 仅转发显式参数；不再默认执行备份或删除历史资产。
控制器先生成审查计划，真实执行必须匹配计划摘要和隔离 project；本机没有执行 Docker、
停服、备份或恢复。D01–D16 全部 BLOCKED，C22 整项仍 open。

### 5.2 备份范围与周期

候选采用停写后的完整物理卷快照：PG 集群、Redis、etcd/MinIO/Milvus、共享审计及启用的
参考服务、IdP、监控持久卷。每份归档有文件级哈希/权限清单；配置、镜像、密钥版本和加密
保管需要独立记录。拟定每 12 小时一次并监测最新完整副本年龄，但**没有安装或启用定时任务**。
RPO ≤24h 不能由计划或文件时间证明；停服窗口、容量与安全保管须先在隔离环境验证。

### 5.3 恢复、回退与历史边界

只向全新 `c22-restore-*` project 的新卷恢复，拒绝覆盖/清库/清卷。使用控制器生成的
`restored-volumes.compose.json` 映射所有外部卷，并用 `deploy/docker-compose.dr-drill.yml`
限制应用自动启动；先核对原始镜像/配置与隔离卷，再显式启动指定存储服务。
字节恢复不会启动 API/worker，也不证明 PG 逻辑内容、Milvus 真实检索或外部副作用安全。
核对、激活、RTO/RPO 与 image/schema 回退步骤以 C22 契约为准；不得自动重放复制出的未知任务。

历史 2026-08-06 演练及约 194 秒记录保留在过程档案中，仅适用于当时版本。旧清库、清卷、
`--rm` 和销毁环境命令不再作为当前操作步骤；旧资产均保留交用户处理。

---

## 六、监控

### 6.1 访问 Grafana

```bash
# 启动监控
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile monitoring up -d

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
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f api

# 特定时间段
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --since 1h api

# Nginx 访问日志
docker compose --env-file .env.prod -f docker-compose.prod.yml exec nginx cat /var/log/nginx/access.log
```

---

## 七、运维操作

### 7.1 候选镜像更新

```bash
# 将 .env.prod 中 BUSINESSAGENT_IMAGE 改为新审查摘要，保留旧摘要供回退
set -o pipefail
docker compose --env-file .env.prod -f docker-compose.prod.yml config --format json \
  | python3 -I -B scripts/check_deployment_contract.py
# 仅上一步 PASS 且已获更新授权后继续
docker compose --env-file .env.prod -f docker-compose.prod.yml pull api worker
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --no-deps --no-build api worker
```

更新会替换容器，可能中断请求，不承诺零停机；Nginx 上游地址解析也需复核，必要时在授权窗口重新加载代理。按 §4.3 重新验收 API/worker 身份和入口；旧摘要可用不等于数据迁移可回退，迁移回退由 C03/C22 明确。当前非删除规则下，不自动执行容器替换或回收。

### 7.2 扩容（多实例）

C09 已提供共享 Redis 取消租约/SSO state 与每请求数据库 Prompt 快照的离线实现；真实双进程、Redis 原子性/TTL/故障、API/SSE/SSO 验收仍 BLOCKED。当前 Compose 的 `--workers 1` 保持不变，也未确认将交付范围收窄为单进程。后续隔离验证须让两个独立 API 进程指向同一套隔离 Redis/PG，并明确将登录/取消/Prompt 更新与后续请求路由到不同进程；详细标准见[跨进程状态契约](../../docs/50-engineering/cross-process-state.md)。Redis 不可用现在会拒绝新聊天/SSO；不要依赖进程内降级。本文不会自动执行扩容或重启。

以下仅为历史扩容参考，跨进程状态由 C09 验收前，不作为已支持能力或当前执行步骤：

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --scale api=2
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

### 7.4 历史清理命令（不属于当前操作流程）

以下仅保留历史命令供识别，**当前非删除规则下不得执行**。保留式恢复与回退只按 §5 和 [C22 契约](../../docs/50-engineering/retained-recovery.md)；容器/卷/镜像回收不在本轮授权中。

```bash
# 停止全部服务(保留数据)
docker compose --env-file .env.prod -f docker-compose.prod.yml down

# 停止并删除数据卷(⚠️ 危险,会丢失全部数据)
docker compose --env-file .env.prod -f docker-compose.prod.yml down -v

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
docker compose --env-file .env.prod -f docker-compose.prod.yml logs api | tail -50

# 常见原因:
# - .env.prod 缺少必填字段(POSTGRES_PASSWORD 等)
# - Milvus/PG/Redis 未就绪(depends_on healthy 检查)
# - 模型路径错误(EMBEDDING_MODEL 不存在)
```

### 9.2 Milvus 检索返回 0 条

```bash
# 检查集合状态
docker compose --env-file .env.prod -f docker-compose.prod.yml exec api \
  python -c "from app.core.milvus_client import get_collection; c = get_collection(); print(c.num_entities)"

# 检查命名空间过滤
# 用户 dept_sales 可访问:本部门文档 + shared_company
```

### 9.3 Redis Checkpointer 失效

C10：`CHECKPOINT_BACKEND=redis` 为默认；所有 API 进程必须一致。后端故障拒绝启动/请求，不自动切到 PG 或 memory。PG 路径需在单独获批的隔离目标先运行显式 schema setup；`memory` 只允许 `APP_ENV=dev`。配置、步骤、TTL、并发与恢复验收见[checkpoint 契约](../../docs/50-engineering/checkpoint-durability.md)。本轮未执行 setup 或调整 worker 数。

```bash
# 检查 RediSearch 模块
docker compose --env-file .env.prod -f docker-compose.prod.yml exec redis redis-cli -a $REDIS_PASSWORD MODULE LIST

# 应包含: search + ReJSON
# 不包含则初始化失败；修复目标服务，禁止用切后端冒充状态恢复
```

### 9.4 磁盘满

```bash
# 查看磁盘占用
docker system df

# 清理日志(json-file 日志会占空间)
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail 0 -f api  # 看实时
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

## C23 capacity candidate

Use the [frozen capacity contract](../../docs/50-engineering/capacity-evidence.md) before
performance work. `eval/run_load_test.sh` now delegates to `eval/run_capacity.py` and requires
an explicit plan; no default load or Docker fallback is performed. The draft rejects unresolved
hardware/image/data/oracle fields. Live execution additionally requires the reviewed plan digest,
a new retained output directory, private TLS and separately authorized isolated accounts/models.
`deploy/Dockerfile.capacity` reuses the application image; package it only after build approval.
L01–L16, real 30-minute load, resource/queue recovery and actual provider cost remain BLOCKED.
Historical health-throughput/k6 reports cannot certify current capacity. No cleanup commands
are supplied. Keep actual runtime output private and link sanitized evidence from the C23 record.


## F2-04 build reproducibility plan — 2026-10-20

Authorized after local `e3831b3`: plan, implement, offline verification, documentation and
OpenSpec review, then local commit only. No image build, push, publication, deployment,
spec sync or archive. Real runtime/full RAG remain BLOCKED; C10 stays OPEN.

Scope is the external-model production candidate (`Dockerfile.prod`, INSTALL_ML=0,
Linux amd64). Development, optional ML, reference IdP/service/capacity images are separate
profiles; their existing behavior is retained without inheriting a reproducibility claim.
The target is reviewed immutable package inputs and explainable inventories, not an
unmeasured promise of identical OCI bytes across hosts or builder versions.

1. Resolve the official Python 3.13 Debian bookworm base and Dockerfile frontend to
   content digests, recording source, platform, Python version and lookup evidence. Use
   the same base in both stages. Freeze Debian repositories to a dated signed snapshot;
   retain signature verification, disable only expired snapshot metadata validity checks.
2. Replace remaining production ranges with exact reviewed versions compatible with
   declared Python support. Generate a separate hash-checked wheel lock from official
   PyPI metadata for all production pins, reject source builds and hidden resolver changes,
   and remove post-lock range upgrades. No new dependencies are authorized or required.
   Existing security upgrades must be represented in reviewed inputs, never bypass scans.
3. Add a standard-library verifier/inventory tool. Validate pins, hashes and recipe inputs
   offline; compare the actual final Python distributions with the expected production set
   (including missing, extra, duplicate and wrong-version rejection). Record Python,
   platform, OS package versions and input hashes in a deterministic inventory, with
   honest separate status for the optional ML experiment. Wire final non-root verification
   into the image and export the actual image inventory/identity as CI evidence before
   publication. Retain existing import probes, pip check, secret/dependency/Trivy gates.
4. Record a controlled update/rebuild procedure: approve input changes, refresh reviewed
   digests and hashes, rerun scans, retain old/new input and installed-package inventories,
   explain changes, and rebuild twice in the same isolated target before runtime acceptance.
   Pinning does not make an outdated dependency safe; availability and freshness are distinct.
5. Test malformed/ranged/duplicate pins, hash/recipe drift, package inventory mismatches,
   optional-profile labeling, deterministic output and CI/context wiring without Docker,
   stores or models. Run relevant offline entries and the full retained test suite with no
   skips. Compare tested bytes and preserve unrelated content and file modes before commit.

Exit: implementation/offline checks may PASS; actual wheel installation on Linux,
snapshot resolution, two clean image builds, installed inventory/import probes and security
scans for this candidate stay BLOCKED until separately run. Strict OpenSpec CLI is also
BLOCKED while unavailable. Wait for confirmation before another finding or remote action.


## F2-04 input contract and update procedure — 2026-10-20

Implementation/offline verification is complete; **F2-04 image/rebuild acceptance remains
OPEN / BLOCKED**. The plan above preceded code. No image was built or published locally.
The application source and schema are unchanged; the NumPy version selection below is
an explicit dependency-input change whose real model/RAG effects remain unaccepted.

| Input / evidence | Current contract |
| --- | --- |
| Production target | INSTALL_ML=0, Linux amd64, CPython 3.13.16, Debian bookworm; CI explicitly requests linux/amd64 |
| Python base | Both stages use `python:3.13.16-slim-bookworm@sha256:f040863673aea2570c3ff6a5c3fb4c673a016cbc5375005ad145915922b6b78a` |
| Dockerfile frontend | `docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e` |
| Debian sources | `debian.sources`: bookworm/main and bookworm-security/main snapshots at 20261107T000000Z; inherited sources disabled by apt options; archive keyring signature checks retained |
| Fixed OS security inputs | apt/libapt-pkg6.0 2.6.2 and openssl/libssl3 3.0.22-1~deb12u2; exact install requests and dpkg version assertions; compare final inventory for other snapshot-driven updates |
| Python packages | 98 exact pins in `requirements-prod.txt`; 114 compatible official wheel hashes in `requirements-prod.lock`; binary-only, hash-required, no resolver-added dependencies in production |
| Reviewed range resolutions | msgpack 1.2.3, setuptools 84.1.0, uvloop 0.22.1; numpy 2.4.6 for current 3.11/3.13 compatibility |
| Input manifest | `build-inputs.json`: registry/platform identities, PyPI metadata provenance and dependency markers, wheel hashes, Debian Release lookup hashes and six input-file hashes |
| Installed evidence | Final non-root build verifier and CI collect exact Python package set, actual dpkg package versions/architecture, Python/platform and input hashes; CI also retains `docker image inspect` output |
| Preserved gates | pip check, PostgreSQL/RS256 imports, frontend verification, secret scanning, pip-audit and Trivy HIGH/CRITICAL gate; inventory verification precedes scan/publication |

The official registry index/manifest/config digest chain was checked over HTTPS for Linux
amd64 and Python 3.13.16; no image layers were downloaded or executed. PyPI release metadata
provided the wheel hashes and dependency markers. Debian Release metadata was readable;
actual apt signature verification/installation is a later build gate, not a local result.
Relevant provenance URLs and metadata SHA-256 values are retained in `build-inputs.json`.
Hashes detect changed inputs; they are not third-party certification or proof of safe code.

NumPy 2.5.1 from the preceding local test environment requires Python >=3.12. Version 2.4.6
keeps the shared exact requirements usable with CI's latest Python 3.11 patch. Metadata
closure tests use 3.11.3 and production 3.13.16. Redis conditionally needs async-timeout on
3.11.0–3.11.2; those old patches are not a closed-set target of this contract. The ordinary
resolver may add that conditional dependency there. The production wheel lock is specifically
3.13/Linux amd64; do not install it on macOS, arm64 or Python 3.11. pyproject/dev requirements,
CI runner, test/audit tools and action tags are not a fully frozen test/toolchain environment.

Run the read-only input check from `enterprise-agent/`:

```bash
python3 -I -B scripts/verify_build.py --root .
```

Default mode only reads input files and prints JSON; it does not inspect the host package
set or run subprocesses. `--installed` additionally reads installed Python metadata and
executes a fixed `dpkg-query -W` command with a 15-second timeout. It requires the exact
production Python/platform and emits JSON to stdout without modifying files, importing the
application, connecting to services or reading .env. Missing/extra/duplicate/wrong-version
Python packages fail verification. Optional `--profile experimental-ml` permits additional
packages but always emits EXPERIMENTAL_NOT_ACCEPTED; base pins still must match. OS package
versions are observations, not an already accepted expected OS package list.

Controlled update and rebuild workflow (commands below are for a separately authorized
isolated Linux environment, **not executed in this increment**):

1. Freeze the Git candidate and proposed dependency/security-update scope. Review new
   Python/platform support and all transitive markers/extras. New dependencies require
   confirmation. Select official registry digests and release-specific PyPI wheels; retain
   lookup metadata/hash evidence. Never reuse a mutable tag as the sole identity.
2. Update exact requirements and the matching production wheel hashes together. Keep
   `--require-hashes --only-binary=:all: --no-deps`; no post-lock upgrades or source builds.
   Refresh the snapshot date and Debian Release provenance together when OS fixes are
   required. Do not disable signature checks or add a mutable fallback if archives fail.
   Snapshot expiration checking alone is disabled for historic metadata replay.
3. Review each changed input, then update its SHA-256 in `build-inputs.json`. Changes to the
   verifier itself also require review/resealing. Run input/adversarial/full tests and inspect
   the diff. Do not blindly regenerate hashes to bless an unexplained mismatch.
4. Record `git rev-parse HEAD`, build arguments (INSTALL_ML=0, APP_VERSION=1.3.0), host
   architecture, Docker/BuildKit versions and scanner/database versions. Build twice with
   separate empty builder caches, the same platform/inputs and reviewed build context:

   ```bash
   docker buildx build --platform linux/amd64 --no-cache --pull --load \
     -f Dockerfile.prod --build-arg INSTALL_ML=0 --build-arg APP_VERSION=1.3.0 \
     -t businessagent:rebuild-a .
   docker buildx build --platform linux/amd64 --no-cache --pull --load \
     -f Dockerfile.prod --build-arg INSTALL_ML=0 --build-arg APP_VERSION=1.3.0 \
     -t businessagent:rebuild-b .
   ```

   Use a fresh builder/cache for each command as recorded by the operator. Retain both
   build logs and each image's inventory and identity. For each image, run read-only:

   ```bash
   docker run --network none --read-only --entrypoint python businessagent:rebuild-a \
     -I -B /build-info/scripts/verify_build.py --root /build-info --installed
   docker image inspect businessagent:rebuild-a
   ```

   Repeat for rebuild-b. Preserve outputs under distinct candidate/run identities. Compare
   Python and OS package maps and input identities. Explain image/config/history differences,
   including timestamps, bytecode, builder metadata, app context and build arguments; stop
   acceptance if differences are unexplained. Same package versions alone do not prove
   byte-for-byte identical OCI images or reproducible source builds.
5. Run the existing secret/dependency/Trivy/import gates against the actual candidate.
   If a pinned input becomes vulnerable or unavailable, propose a reviewed refresh and
   retain previous evidence; never keep it indefinitely solely to preserve a digest or
   bypass scans. Publication remains separately authorized. C01/C24/runtime/full RAG and
   C10 are not closed by this procedure or by the installed-set verifier.

Development Dockerfile, INSTALL_ML=1, reference IdP/service and derived capacity images
retain their own current contracts; none inherits the production reproducibility claim.
The optional ML branch retains build tools using the same snapshot, permits its existing
resolver experiment and records an explicitly unaccepted inventory. This is not a license
inventory/SBOM, signature rollout, F2-09 closure, real customer usage or deployment approval.

## F2-04 offline delivery evidence — 2026-10-20

- **PASS:** 50 new adversarial cases; final full pytest **1098 tests + 249 subtests**, zero
  skips, xfails or guard denials. Prior focused run: 76 tests + 34 subtests before four
  additional CLI/metadata cases. Existing application coverage is 75.64%; that percentage
  excludes the standalone verifier script and is not its coverage claim.
- **PASS:** read-only production input verifier (98 packages), Dockerfile standalone four
  checks and safe_validate execution. safe_validate exits 2 / overall BLOCKED because real
  UAT/release evidence is still absent; its execution PASS is not formal acceptance.
- First full run exposed a metadata-test assumption of Python 3.11.0. The Redis conditional
  dependency boundary was documented and the actual CI/production patch baselines made
  explicit; no test was skipped and no new dependency was added.
- Full receipt: `enterprise-agent/eval/results/ci-pytest-9c0b64c525304088a00ccc4a72f5d8c3/receipt.json`.
  Related receipts, registry proof, validation and local commit binding are retained next
  to it. macOS arm64/Python 3.13.15 tests use an isolated declared-dependency view with the
  SHA-256-checked NumPy 2.4.6 wheel. Metadata/wheel lookup is separate from network-denied
  tests; no machine-wide installation, image build, model/store/business API call occurred.
- Diff/source review, Python 3.11 syntax, YAML/local links/manual OpenSpec structure,
  tested-byte binding and original modes/unrelated content are checked before commit.
  OpenSpec CLI is unavailable; strict CLI validation stays **BLOCKED**.

F2-04 is **IMPLEMENTED / OFFLINE VERIFIED; IMAGE/REBUILD ACCEPTANCE OPEN / BLOCKED**.
Two real Linux builds, actual apt/wheel installation and image inventory, current scans,
remote CI, all prior runtime matrices and full RAG remain BLOCKED; C10 stays OPEN.
Local commit only, then wait for confirmation; no push/merge/release/deployment/spec sync/
archive or next finding.


### Integrated approval and authentication safety (local candidate)

This integration has not been deployed or accepted for runtime use. Preserve the C03
managed bootstrap path above; do not run historical initialization SQL against an existing
database. Production authentication requires individual passwords and rejects the bundled
demo password hash. Create administrators through the managed bootstrap command documented
in DATABASE_BOOTSTRAP.md, not by reintroducing shared defaults. Existing deployments need
an independently authorized credential/old-session review and JWT rotation before exposure;
verify correct individual credentials succeed and incorrect/demo credentials fail.

Approval acceptance records a decision only. The original requester must separately confirm
execution. A failed multi-action plan stops for human review, with no automatic compensation.
Uncertain outcomes remain held even after late receipts; receipts are evidence, not permission
to continue. Preserve operation journals and do not reset/requeue unknown outcomes.

The managed schema retains C10 version 8 and adds approval-contract guards as version 9.
Stop all older API/executor/worker instances before any separately approved migration or
rollout. Do not mix old executors with new contracts, backfill legacy provenance, remove guards
to roll back, or start old automatic-compensation workers against retained queues. Reconcile
legacy/manual holds with an authorized human and reviewed evidence. Offline checks do not
authorize migration, deployment, live provider calls or hold clearance.
