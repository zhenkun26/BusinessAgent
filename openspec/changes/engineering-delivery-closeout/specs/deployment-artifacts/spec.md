## ADDED Requirements

### Requirement: 部署必须使用同一不可变应用镜像
生产 Compose SHALL 让 API 与 worker 引用同一 registry digest，不包含应用 build 或源码覆盖挂载；候选来源 SHALL 能追溯到使用 Dockerfile.prod 的构建/扫描记录。

#### Scenario: 候选产物部署前核验
- **WHEN** 渲染部署配置并运行契约检查
- **THEN** API/worker 同为明确的 sha256 镜像引用，配置不含本地构建、源码覆盖或应用宿主端口，否则阻断部署步骤

#### Scenario: 服务运行后核验
- **WHEN** 在隔离目标环境启动候选
- **THEN** API/worker 的实际 image ID 与候选摘要解析结果相同，证据记录提交、摘要与实际 ID，不以容器 running 代替成功

### Requirement: 入口必须支持已声明的产品路径
HTTPS 入口 SHALL 提供 UI、API、健康、就绪及 API 文档和 schema，根路径 SHALL 跳转 UI；未知路径 SHALL 返回 404。

#### Scenario: 同源用户流程
- **WHEN** 用户从 HTTPS 根路径进入并登录、查看 API 文档及发起 SSE 对话
- **THEN** UI 与 API 同源可达，文档可加载 openapi.json，流式响应不被代理缓冲或错误的 Upgrade 头阻断

### Requirement: 指标与 worker 健康不得误暴露或误判
公共入口 SHALL 拒绝 metrics 读取，监控 SHALL 走内部网络；worker SHALL 不使用 API HTTP 探针，并明确当前没有专用就绪验收。

#### Scenario: 公开访问指标
- **WHEN** 外部访问 /metrics 或其子路径
- **THEN** 返回 404，API 宿主端口未发布，内部 Prometheus 仍可按配置采集

#### Scenario: 无运行环境
- **WHEN** 只有配置解析或离线测试，未运行真实代理/镜像
- **THEN** 配置检查可标 PASS，但目标环境 UI/登录/SSE/镜像身份验收保持 BLOCKED，不宣称 C01 完成
