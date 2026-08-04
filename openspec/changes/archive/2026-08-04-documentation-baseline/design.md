## Context

现状与约束（动机见 proposal.md）：

- 仓库根目录散落 10 个 md、`前置准备/` 7 个方案/研究文件、`产品介绍网页/` 演示资产；`enterprise-agent/` 内部另有 README/DEPLOY 工程文档与 `eval/sample_docs/` 知识数据。
- 项目无 Git 仓库（`git status` 报 not a git repository），无任何版本历史。
- `openspec/specs/` 主规格目录为空；`openspec/changes/` 下已有进行中的 `complete-business-processes`（6 能力、41 任务、0 完成），本次 change 与其互不干扰。
- 文档内存在大量交叉引用：根目录 md 之间互链、md 内嵌 `file:///d:/...` 绝对路径（Windows 开发机遗留）、相对链接。
- 用户已拍板：Git 初始化；迁移到 `docs/`；面试备稿与演示资产独立为 `interview/`；本 change 单独承载；全中文、保持现有写作风格；六大层分类 + 版本整理 + openspec 规范化；根目录新增带注释的 `contents.md`。

## Goals / Non-Goals

**Goals:**

- 建立六大层文档目录（产品方案层 / 产品文档层 / 操作手册层 / 过程记录层 / 工程文档层 / 知识数据库层），每个文件有确定归属。
- 完成 Git 初始化与分阶段基线提交，全部内容纳入版本管理且敏感文件被排除。
- 落地 `contents.md`（全仓库目录树 + 每行用途注释）、`CHANGELOG.md`、`ROADMAP.md`、`DECISIONS.md`、`ISSUES.md`。
- 完成 openspec 规范化：config context 补全 + 四个文档类能力沉淀为主规格。
- 迁移后全部相对链接与交叉引用有效，README 成为唯一导航入口。

**Non-Goals:**

- 不修改 `enterprise-agent/` 任何业务代码，不触碰 `complete-business-processes` 的功能实施范围。
- 不重写各文档正文内容（只做结构迁移、版本头更新、链接修正、记录迁移）。
- 不引入 CI、文档站点生成器（如 MkDocs/Docusaurus）等新工具链；`contents.md` 与 README 即为导航。
- 不移动 `eval/sample_docs/` 知识数据与 `enterprise-agent/` 工程文档，仅建立索引。

## Decisions

### 1. docs/ 目录编号与命名

采用「编号 + 英文 slug」目录，编号保证排序稳定与预留扩展位，英文 slug 保证工具链友好，层名（中文）在目录 README 与 contents.md 注释中标注：

```
docs/
├── 00-overview/          # 元层:项目概览与导航说明
├── 10-product-plan/      # 产品方案层
├── 20-product/           # 产品文档层
├── 30-guides/            # 操作手册层
├── 40-process/           # 过程记录层(进度/决策/问题)
├── 50-engineering/       # 工程文档层(索引)
├── 60-knowledge/         # 知识数据库层(索引)
└── 90-archive/           # 归档层(历史版本)
```

备选：纯语义命名（product/guides/process…）。否决：无法表达层次优先级，新目录插入会打乱既有相对顺序；编号目录在 `ls` 与文件选择器中天然有序。

### 2. 现有文件迁移映射（单一事实源）

| 现有路径 | 迁移目标 | 说明 |
|---|---|---|
| 产品文档.md | docs/20-product/ | 版本头升 v1.2 + 校验日期 + commit |
| 使用案例手册.md | docs/30-guides/ | 原地改名不动内容 |
| 产品使用手册-前端版.md | docs/30-guides/ | 同上 |
| 运维维护手册.md | docs/30-guides/ | 第 8 节变更记录迁移至 ISSUES.md，手册保留简版并链接 |
| 阶段性总结_W2-W6.md / _W7-W9_联调.md | docs/40-process/ | 沿用命名，后续迭代按模板追加 |
| 临时备忘.md | docs/40-process/ | 决策与 P3 事项拆入 ROADMAP/ISSUES 后归档 |
| 前置准备/企业知识工作流Agent产品方案_v3_整合版.md | docs/10-product-plan/ | 现行方案基线 |
| 前置准备/deep-research-report*.md ×3 | docs/10-product-plan/research/ | 选型研究依据 |
| 前置准备/企业知识工作流Agent产品方案.md（v1）/ _v2_LangGraph版.md / 改进文档.md | docs/90-archive/ | 历史版本，被 v3 与实现取代 |
| Agent项目面试备稿.md | interview/ | 独立体系 |
| 产品介绍网页/ | interview/产品介绍网页/ | 整目录迁移（截图/字体相对路径不受影响） |
| 业务流程图.png | docs/20-product/assets/ | 产品文档配图 |
| enterprise-agent/README.md、deploy/DEPLOY.md | 原地保留 | docs/50-engineering/README.md 索引 |
| eval/sample_docs/ ×7 | 原地保留 | docs/60-knowledge/README.md 索引 |

### 3. Git 初始化与提交策略

分三个提交，便于按阶段回滚：

1. **基线提交**（`docs-baseline: 现状快照`）：git init + .gitignore 校验后提交当前全量（此刻尚未移动任何文件）。
2. **结构迁移提交**（`docs-baseline: 目录结构迁移`）：docs/、interview/、contents.md、CHANGELOG.md 及全部移动与新建文件。
3. **基建收尾提交**（`docs-baseline: 导航与记录规范化`）：README 重写、链接修复、openspec config/主规格、ROADMAP/DECISIONS/ISSUES。

.gitignore 在现有 411 字节基础上校验补充：`.venv_e2e/`（已含 `.venv_*`）、`backups/`、`*.log` 等；提交前用 `git status` 人工核对无 `.env` 等敏感文件。

### 4. contents.md 格式

以 `tree` 命令输出为基础整理为手写 Markdown 代码块，每一行 `#` 注释写明用途；`enterprise-agent/` 等深目录只列到一级并注明「详见该目录内部文档」，避免索引过长：

```text
BusinessAgent/
├── README.md                 # 全仓库唯一导航入口
├── contents.md               # 本文件:目录树索引(每行注释用途)
├── CHANGELOG.md              # 版本变更日志(时间倒序)
├── AGENTS.md                 # Codex 项目说明与工程约定
├── docs/                     # 统一文档体系(六大层 + 归档)
│   ├── 10-product-plan/      # 产品方案层:现行方案与研究依据
│   ├── 20-product/           # 产品文档层:产品文档.md 为权威现状
│   ├── 30-guides/            # 操作手册层:使用案例/前端版/运维手册
│   ├── 40-process/           # 过程记录层:总结/ROADMAP/DECISIONS/ISSUES
│   ├── 50-engineering/       # 工程文档层:索引 enterprise-agent 内部文档
│   ├── 60-knowledge/         # 知识数据库层:索引 eval/sample_docs
│   └── 90-archive/           # 归档层:历史方案与淘汰文档
├── interview/                # 面试与演示资产独立体系
├── enterprise-agent/         # 后端工程(README/DEPLOY 由 50-engineering 索引)
└── openspec/                 # openspec 变更与主规格
```

### 5. openspec 规范化路径

- `openspec/config.yaml` 补全 `context`：技术栈（Python 3.11 / FastAPI / LangGraph / Milvus / PG / Redis / Ollama）、工程约定（PEP 8、全量类型注解、中文文档）、文档六大层规范。
- 本 change 实施完成后用 `openspec sync-specs` 把四个 delta specs 并入 `openspec/specs/` 主规格，再 `openspec validate` 校验后归档。
- `complete-business-processes` 保持独立，不随本 change 归档。

### 6. 链接修正策略

- 根目录 md 之间相对链接：按迁移后相对路径重写。
- `file:///d:/...` 绝对路径：全部改为仓库内相对路径或删除（保留到代码文件的具体行引用时改用相对路径 + 行号说明）。
- 文档头「关联文档」段：改为指向 docs/ 与 interview/ 的新路径。
- 校验手段：迁移后 `rg -n "file://|\.\./|\./.*\.md" docs/ interview/` 逐条核对；`docs/` 内用脚本断言相对链接目标存在。

## Risks / Trade-offs

- [迁移后链接大面积失效] → 采用 git mv 保留历史、迁移与链接修正同提交完成、提交前用脚本校验相对链接目标存在。
- [基线提交误含敏感文件] → 提交前 `git status` + `git ls-files | rg -i "\.env|secret|key"` 双检查，`.gitignore` 先行落地。
- [docs 与代码现状脱节（README 进度表已过时）] → 本轮 README 重写时以代码与 openspec 状态为准对账，修正「剩余工作」等过时表述。
- [面试备稿内嵌绝对路径失效] → 迁移时同步改写其中的 `file:///d:/` 引用为相对路径。
- [移动后使用手册/产品文档的「关联文档」指向旧位置] → 迁移映射表作为单一事实源，收尾校验 grep 确认无旧路径残留。

## Migration Plan

1. `.gitignore` 校验补充 → `git init` → 基线提交（现状快照）。
2. 创建 `docs/` 八目录骨架与 `interview/`，按迁移映射表移动文件（git mv）。
3. 更新文档版本头与交叉引用；新建 `contents.md`、`CHANGELOG.md`、`ROADMAP.md`、`DECISIONS.md`、`ISSUES.md`；从运维手册第 8 节迁移坑记录。
4. 新建 `docs/50-engineering/README.md`、`docs/60-knowledge/README.md` 索引；更新 `AGENTS.md` 目录结构说明。
5. 重写根 `README.md` 为导航入口；更新 `openspec/config.yaml` context；执行 `openspec sync-specs` 沉淀主规格；`openspec validate`。
6. 全量校验（目录树 vs contents.md、链接检查、git status 无敏感文件）后提交结构迁移与基建收尾两个 commit。
7. 回滚策略：任一步骤失败可 `git reset` 回上一提交；目录移动失败可用 `git mv` 反移。

## Open Questions

无（用户已对 Git 初始化、迁移方式、interview 体系、change 拆分、语言风格、六大层分类、contents.md 逐项拍板；迁移映射表已在本设计定案，不阻塞实施）。
