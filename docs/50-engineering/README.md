# 50-engineering · 工程文档层

本层提供工程文档索引与跨模块交付契约。实现、部署与操作说明保留在代码目录内；交付基线只定义范围和验收证据，不复制实现说明。

## 索引

| 文档 | 位置 | 用途 |
|---|---|---|
| 工程交付基线 | [engineering-delivery-baseline.md](engineering-delivery-baseline.md) | 单组织单机支持边界、参考集成、验收证据与工程完成条件 |
| 离线安全验证入口 | [safe-validation.md](safe-validation.md) | C24 前置：允许范围、副作用审查、执行方式、输出状态与限制 |
| 后端 README | [enterprise-agent/README.md](../../enterprise-agent/README.md) | 快速开始、项目结构、实施进度、技术栈 |
| 生产部署指南 | [enterprise-agent/deploy/DEPLOY.md](../../enterprise-agent/deploy/DEPLOY.md) | 部署架构、备份恢复、监控、安全清单 |

## 约定

- 工程文档随代码维护，不在 `docs/` 复制内容。
- 新增工程文档（如架构图、接口规范）时，先在此层登记索引。
