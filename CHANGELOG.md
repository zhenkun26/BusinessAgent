# CHANGELOG · 版本变更日志

> 按时间倒序记录功能与文档版本变更。版本号与文档头保持一致；每次迭代在顶部追加一条。

## v0.1 · 文档基线（2026-08-04）

### 变更摘要

- 初始化 Git 仓库，建立基线提交（`b4cca93`）、结构迁移提交（`cb560d5`）、基建收尾提交（本提交）。
- 根目录文档全部迁入 `docs/` 六大分层（产品方案 / 产品文档 / 操作手册 / 过程记录 / 工程文档 / 知识数据库）+ `90-archive` 归档层；`前置准备/` 目录移除。
- 面试备稿与演示资产独立为 `interview/` 体系。
- 新增根目录 `contents.md`（全仓库目录树 + 每行用途注释）与 `README.md`（唯一导航入口）。
- 新增 `docs/40-process/ROADMAP.md`（里程碑规划）、`DECISIONS.md`（决策记录）、`ISSUES.md`（问题/坑/backlog）。
- openspec 规范化：`openspec/config.yaml` 补全项目 context；`documentation-baseline` change 四能力规格沉淀为 `openspec/specs/` 主规格。
- 文档版本头统一（版本号 + 校验日期 + 对应 commit），交叉引用与 `file:///d:/` 绝对路径修正。

### 兼容性说明

- 旧文档路径（根目录 *.md、`前置准备/`、`产品介绍网页/`）不再有效，全部迁移至新路径，无内容删除。
