# version-control Specification

## Purpose

为项目建立 Git 版本控制与文档版本管理规范，使每一次文档与代码变更都可追溯、可回滚、可审计，并保证敏感信息永不进入版本历史。

## Requirements

### Requirement: 项目必须纳入 Git 版本控制

系统 SHALL 将仓库纳入 Git 版本控制，初始化后 SHALL 建立包含当前全部文档与代码的基线提交；后续所有变更 SHALL 通过 Git 提交记录，且提交粒度 SHALL 按「功能或文档迭代」成组，便于按阶段回滚。

#### Scenario: 初始化后存在版本历史
- **WHEN** 在仓库根目录执行 `git log`
- **THEN** 能看到从基线提交开始的完整提交历史

#### Scenario: 变更可回滚
- **WHEN** 某次文档或代码变更出现问题
- **THEN** 可通过 Git 回退到变更前的提交，恢复文件原状

### Requirement: 敏感文件必须被排除在版本控制之外

系统 SHALL 通过 `.gitignore` 排除环境变量、密钥、日志、运行时数据、模型文件、虚拟环境、评测结果等敏感或可再生文件；任何提交 SHALL 不包含 `.env` 类密钥文件。

#### Scenario: 敏感文件不进版本库
- **WHEN** 检查 `git status` 与已提交文件
- **THEN** `.env`、日志、模型目录、`.venv_*`、`eval/results/` 等均不在版本控制范围内

### Requirement: 文档变更必须记录到 CHANGELOG

系统 SHALL 在根目录维护 `CHANGELOG.md`，按时间倒序记录每次功能与文档版本变更（版本号、日期、变更内容）；文档层任何结构性变更 SHALL 在 CHANGELOG 中留痕。

#### Scenario: 迭代后追加变更记录
- **WHEN** 完成一次功能或文档迭代
- **THEN** `CHANGELOG.md` 顶部新增一条含版本号、日期与变更摘要的记录

### Requirement: 文档必须携带版本头

系统 SHALL 在核心文档（产品文档、各手册、产品方案）文件头部携带版本信息：版本号（vX.Y）、最后校验日期、对应代码 commit（或提交范围），使读者能判断文档与代码现状的对应关系。

#### Scenario: 核心文档版本可读
- **WHEN** 打开产品文档或手册文件头
- **THEN** 能看到版本号、校验日期与代码 commit 引用
