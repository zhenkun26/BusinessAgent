## 1. Git 版本控制初始化

- [x] 1.1 校验并补充 `.gitignore`（覆盖 `.venv_e2e/`、`backups/`、`*.log` 等；确认 `.env`/密钥/模型目录已排除）
- [x] 1.2 在仓库根目录执行 `git init`
- [x] 1.3 提交基线快照（commit 1：`docs-baseline: 现状快照`），提交前核对 `git status` 与 `git ls-files` 无敏感文件

## 2. 目录骨架与文件迁移（documentation-layout）

- [x] 2.1 创建 `docs/` 八目录骨架（00-overview / 10-product-plan / 20-product / 30-guides / 40-process / 50-engineering / 60-knowledge / 90-archive）与 `interview/`
- [x] 2.2 迁移产品方案层：`前置准备/企业知识工作流Agent产品方案_v3_整合版.md` → `docs/10-product-plan/`；3 份 deep-research 报告 → `docs/10-product-plan/research/`
- [x] 2.3 归档历史方案：`前置准备/企业知识工作流Agent产品方案.md`（v1）、`_v2_LangGraph版.md`、`改进文档.md` → `docs/90-archive/`
- [x] 2.4 迁移产品文档层：`产品文档.md` → `docs/20-product/`，版本头更新为 v1.2 + 校验日期 + commit 引用
- [x] 2.5 迁移操作手册层：`使用案例手册.md`、`产品使用手册-前端版.md`、`运维维护手册.md` → `docs/30-guides/`
- [x] 2.6 迁移过程记录层：`阶段性总结_W2-W6.md`、`阶段性总结_W7-W9_联调.md`、`临时备忘.md` → `docs/40-process/`
- [x] 2.7 迁移配图：`业务流程图.png` → `docs/20-product/assets/`
- [x] 2.8 迁移面试与演示体系：`Agent项目面试备稿.md` 与 `产品介绍网页/` 整目录 → `interview/`
- [x] 2.9 建立工程文档层索引：新建 `docs/50-engineering/README.md`，指向 `enterprise-agent/README.md` 与 `deploy/DEPLOY.md`
- [x] 2.10 建立知识数据库层索引：新建 `docs/60-knowledge/README.md`，指向 `eval/sample_docs/` 7 份知识文档并附入库规范摘要
- [x] 2.11 更新 `AGENTS.md` 目录结构说明与关键文档链接（指向 docs/ 与 interview/ 新路径）
- [x] 2.12 提交结构迁移（commit 2：`docs-baseline: 目录结构迁移`）

## 3. 版本管理规范落地（version-control）

- [x] 3.1 新建根目录 `CHANGELOG.md`，按时间倒序录入基线条目（含版本号、日期、变更摘要）
- [x] 3.2 为 `docs/20-product/产品文档.md` 与三本手册补齐版本头（版本号、最后校验日期、对应 commit）
- [x] 3.3 全量修正交叉引用：重写根目录 md 之间相对链接，删除或改写 `file:///d:/...` 绝对路径为仓库内相对路径

## 4. 进度与问题记录（progress-issue-records）

- [x] 4.1 新建 `docs/40-process/ROADMAP.md`：里程碑规划（已完成 W2-W9 + P1/P2、进行中 complete-business-processes、P3 挂起事项）
- [x] 4.2 新建 `docs/40-process/DECISIONS.md`：从产品文档第十章与面试备稿提炼既有决策记录（背景/决策/放弃/改判条件）
- [x] 4.3 新建 `docs/40-process/ISSUES.md`：迁移运维手册第 8 节坑记录与临时备忘中的 P3 事项（状态/优先级/现象/根因/修复/验证/日期）
- [x] 4.4 运维维护手册第 8 节改为简版摘要并链接 ISSUES.md 全文
- [x] 4.5 建立阶段性总结模板文件（后续迭代沿用现有 W2-W9 格式）

## 5. openspec 规范化（openspec-normalization）

- [x] 5.1 更新 `openspec/config.yaml`：补全 project context（技术栈、工程约定、文档六大层规范）
- [x] 5.2 执行 `openspec sync-specs` 将本 change 四个 delta specs 并入 `openspec/specs/` 主规格
- [x] 5.3 运行 `openspec validate` 确认校验通过

## 6. 导航与收尾

- [ ] 6.1 重写根目录 `README.md` 为全仓库唯一导航入口（各层文档链接 + 常用命令 + 维护入口）
- [ ] 6.2 新建根目录 `contents.md`：完整目录树 + 每一行注释用途，与磁盘实际结构一致
- [ ] 6.3 全量校验：目录树 vs contents.md 对照、相对链接目标存在性检查（`rg` + 脚本断言）、`git status` 无敏感文件
- [ ] 6.4 回归确认：`enterprise-agent/` 代码路径与 `complete-business-processes` 实施范围未受影响
- [ ] 6.5 提交基建收尾（commit 3：`docs-baseline: 导航与记录规范化`）
- [ ] 6.6 确认 `openspec validate` 通过后等待归档（用户确认后执行 `openspec archive`）
