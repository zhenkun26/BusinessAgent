## Why

项目经过 W2-W9 与 P1/P2 迭代，功能闭环已完整，但文档体系没有同步演进：36 个 md 文件散落在仓库根目录与各子目录，产品方案 v1/v2/v3 与实现现状脱节，进度、决策、坑记录分散在多个文件中互相重叠，且整个项目尚无 Git 版本历史，任何变更都不可追溯、不可回滚。文档处于「能看懂、但无法维护、无法随迭代演进」的状态，需要一次性建立文档基线。

## What Changes

- **BREAKING（目录结构）**：根目录 10 个散落 md 全部迁移到 `docs/` 六大分层目录（产品方案层 / 产品文档层 / 操作手册层 / 过程记录层 / 工程文档层 / 知识数据库层），旧路径不再有效。
- **面试与演示资产独立体系**：`Agent项目面试备稿.md` 与 `产品介绍网页/` 迁移到独立的 `interview/` 目录。
- **根目录新增 `contents.md`**：放置本文件夹的完整目录树，每一行用注释写明该文件/目录的作用，作为全局索引。
- **根目录新增 `CHANGELOG.md`**：按时间倒序记录每次功能与文档版本变更。
- **Git 版本控制初始化**：`git init` + `.gitignore` 校验 + 分阶段基线提交，全部文档与代码从此纳入版本管理。
- **进度与问题记录规范**：新增 `docs/40-process/ROADMAP.md`（里程碑规划）、`DECISIONS.md`（决策记录）、`ISSUES.md`（问题/坑/backlog），并从运维维护手册第 8 节迁移坑记录，实现单一事实源。
- **README.md 重写**：由「项目说明」升级为全仓库唯一导航入口，汇总各层文档链接。
- **openspec 规范化**：`openspec/config.yaml` 补全项目 context（技术栈/工程约定/文档规范），本 change 的四个文档类能力规格沉淀为 `openspec/specs/` 主规格，后续需求一律走 openspec change 生命周期。

## Capabilities

### New Capabilities

- `documentation-layout`: 统一文档目录布局与分类体系（docs/ 六大层 + interview/ + contents.md 索引 + README 导航）
- `version-control`: Git 版本控制初始化与文档版本管理规范（基线提交、CHANGELOG、版本头格式）
- `progress-issue-records`: 进度记录与问题留存规范（ROADMAP / 阶段性总结 / DECISIONS / ISSUES，单一事实源）
- `openspec-normalization`: openspec 配置与规格体系规范化（config context 补全、主规格沉淀、变更生命周期）

### Modified Capabilities

<!-- openspec/specs/ 下尚无已发布主规格，本轮全部按新能力处理。 -->

## Impact

- 文件系统：仓库根目录结构重组（新增 `docs/`、`interview/`、`contents.md`、`CHANGELOG.md`、`docs/40-process/` 记录文件）。
- 文档：根目录 10 个 md + `前置准备/` 7 个方案文件 + `产品介绍网页/` 目录迁移；全部交叉引用与相对链接同步修正。
- 工具链：Git 仓库初始化；`openspec/config.yaml` 更新；`openspec/specs/` 主规格目录首次写入。
- 不影响：`enterprise-agent/` 代码工程（仅文档索引指向其内部 README/DEPLOY）、`openspec/changes/complete-business-processes` 的功能实施范围、知识库数据（`eval/sample_docs/` 原地保留并由索引承接）。
