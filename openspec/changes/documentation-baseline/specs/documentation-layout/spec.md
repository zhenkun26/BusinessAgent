## Purpose

建立统一的文档目录布局与分类体系，让项目内每一类文档都有确定的归属位置、索引入口与导航路径，消除根目录散落、多层重复与「找不到最新文档」的问题。

## ADDED Requirements

### Requirement: 文档必须按六大层分类存放

系统 SHALL 将项目文档组织在 `docs/` 目录下，并按产品方案层、产品文档层、操作手册层、过程记录层、工程文档层、知识数据库层六个层次分类存放；每层有独立子目录，任何新建文档 SHALL 先归类再落盘，不得散落在仓库根目录。

#### Scenario: 新文档创建时归类
- **WHEN** 项目新增一份文档（如新的阶段性总结或手册）
- **THEN** 该文档按内容所属层次放入 `docs/` 对应子目录，根目录不新增散落文档

#### Scenario: 六大层目录齐备
- **WHEN** 检查 `docs/` 目录结构
- **THEN** 产品方案层、产品文档层、操作手册层、过程记录层、工程文档层、知识数据库层六个子目录均存在且各含 README 或索引说明

### Requirement: 根目录必须提供 contents.md 目录索引

系统 SHALL 在仓库根目录维护 `contents.md`，内容为整个仓库的目录树（含 `docs/`、`interview/`、`enterprise-agent/` 等全部主要路径），并且目录树的每一行 SHALL 以注释形式说明该文件或目录的作用；新增或移动文件后 SHALL 同步更新该索引。

#### Scenario: 索引覆盖全仓库
- **WHEN** 读者打开根目录 `contents.md`
- **THEN** 能按目录树找到仓库中每一类文件，且每行注释说明该路径的用途

#### Scenario: 文件变动后索引同步
- **WHEN** 目录结构中新增、移动或删除文件
- **THEN** `contents.md` 中的目录树与注释同步更新，与磁盘实际结构一致

### Requirement: 面试备稿与演示资产必须独立成体系

系统 SHALL 将面试相关文档（如 `Agent项目面试备稿.md`）与演示资产（如 `产品介绍网页/`）统一存放在独立的 `interview/` 目录下，与产品/技术文档体系分离。

#### Scenario: 面试与演示资产归位
- **WHEN** 检查 `interview/` 目录
- **THEN** 面试备稿与产品介绍网页（含截图、字体、HTML）均在其中，且 `contents.md` 有对应索引条目

### Requirement: 工程文档与知识库数据原地保留并由索引承接

系统 SHALL 保留 `enterprise-agent/` 内部的工程文档（README、deploy/DEPLOY.md）与知识库数据（eval/sample_docs/）的原始位置，不在 `docs/` 中复制内容；`docs/` 下对应层次 SHALL 提供索引说明，指向这些原地文件。

#### Scenario: 工程文档索引
- **WHEN** 在文档体系内查找工程文档
- **THEN** `docs/` 工程文档层提供指向 `enterprise-agent/README.md` 与 `deploy/DEPLOY.md` 的索引，不产生内容副本

#### Scenario: 知识数据索引
- **WHEN** 在文档体系内查找知识库数据
- **THEN** `docs/` 知识数据库层提供指向 `eval/sample_docs/` 的索引与入库规范摘要，不移动原始数据

### Requirement: README 必须是全仓库唯一导航入口

系统 SHALL 让根目录 `README.md` 成为全仓库唯一导航入口，汇总各层文档链接、常用命令与维护入口；其他文档 SHALL 通过链接引用而非重复搬运导航信息。

#### Scenario: 从 README 到达任意文档
- **WHEN** 新成员从根目录 `README.md` 开始浏览
- **THEN** 可以顺链接到达产品方案、产品文档、各手册、进度与决策记录、面试与演示资产
