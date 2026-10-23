# AI-PM 学习与实践流程 · v1

[English](README-en.md)

用真实决策记录练习问题定义、决策取舍、验证和复盘。每轮先保留你的判断，AI 再针对缺口追问，最后才展示历史过程。成功可以是继续、改判、补证据或停止。

## 从这里开始

向 AI 发送以下启动指令即可开始，暂不需要安装任何工具：

> 请按 BusinessAgent-workflow/workflow/coaching.md 带我练习 BA-01。先只读取 coaching.md、human-gates.md 和 cases/businessagent/model-routing/brief.md，不读取 review.md、sources.md 或它们链接的历史结果。第一轮只给初始情境，问一个开放问题，等我先判断。不要代填我的回答，不要自动写文件或执行实验。

第二个案例使用 `EXT-01`，把路径换为 `cases/external/process-sizing/brief.md`。你已看过前期分析，可能知道部分答案；如实标记为“已接触”，通过后续变化情境检验迁移能力，不称作盲测。

## 阅读路径

| 内容 | 入口 |
| --- | --- |
| 阶段、输入输出、轻量使用方式 | [流程](workflow/lifecycle.md) |
| 先判断、再追问、再揭示 | [辅导协议](workflow/coaching.md) |
| 三个人工确认点与权限边界 | [人工确认](workflow/human-gates.md) |
| 真实来源、归属、日期与验证结论 | [证据规则](workflow/evidence-policy.md) |
| 两个案例与能力目标 | [案例索引](cases/index.md) |
| 已完成的两轮对话与后续练习 | [学习记录](runs/README.md) · [联合复盘](runs/2026-10-23-retrospective.md) |
| GitHub 参考与选择性借鉴 | [参考项目](references/repositories.md) |
| 本版范围、检查和剩余验证 | [交付记录](workflow/delivery.md) |

六种可组合模板：[问题](templates/problem.md)、[方案](templates/options.md)、[实验](templates/experiment.md)、[观察](templates/observations.md)、[决策](templates/decision.md)、[复盘](templates/retrospective.md)。小问题可以放在一篇记录中，不必填满每个模板。未知项保留未知。

## 两个案例

- **BA-01：模型路由判断。** [开始练习](cases/businessagent/model-routing/brief.md)。学习竞争解释、验证设计，以及按具体任务调整决策。历史结果位于单独文件，开始前不要打开。
- **EXT-01：流程深度与交付检查。** [开始练习](cases/external/process-sizing/brief.md)。学习流程裁剪、状态与证据的区别，以及测试漏检。来源是公开仓库的计划和交接记录，不把虚构客户故事当作真实商业验证。

## 使用与记录

默认先在对话中练习。得到保存授权后，再创建 `runs/<date>-<topic>/session.md`，记录案例、模式、已读材料、原始回答、提示、修订和 G1/G2/G3 确认。按需加入上述模板；不预建空白练习和学习档案。不要把 AI 生成的示范答案写成你的学习成果。

文档正文以英文为主；中文入口、辅导话术、你的原始回答和中文历史摘录保留中文。当前为手工对话流程，没有程序强制隐藏答案或验证状态。

2026-10-23 的 [BA-01](runs/2026-10-23-ba-01/session.md) 和 [EXT-01](runs/2026-10-23-ext-01/session.md) 已按后续保存授权整理：保留 18 个原始回答、追问、历史揭示和复盘，区分独立提出的具体判断、提示后补充、看过历史后的修订，以及虚构情境迁移。记录包含答案，不作为新一轮练习的初始材料；这些选定的学习记录已按后续明确授权纳入纯文档发布；完整本地会话日志不公开。

## 本轮及后续边界

初版只新增本目录内的流程文档、模板、两个案例及来源索引。后续授权增加上述两轮学习记录与联合复盘，仍只整理文档。现有 BusinessAgent 的代码、文档、OpenSpec、验收结论和本地已有改动保持原样。

发布分支基于已公开的 `main`，仅增加 `BusinessAgent-workflow` 内的 25 份文档：初版 21 份加上本次 4 份学习记录与复盘。案例中的两份后期来源仍仅为本地证据，未随分支发布；来源表明确区分公开材料、本地材料和用户说明。原本地文档分支及其工程历史保留，不随本次上传。

按 2026-10-23 的用户决定，未来重构在另一个新文件夹进行，并使用本流程，不使用 OpenSpec。新目录名称、位置、架构与迁移方案尚未决定；本轮不创建该目录、不复制代码、不启动重构。现有项目仍保留它原有的规则，本目录不修改或废止它们。工作流本身无 OpenSpec 依赖。

两轮练习已经完成对话层面的判断与复盘；这支持对本次回答的观察，不代表学习保持、实际方案效果或流程收益已验证。后续练习仍是提议，原项目运行验收和未来重构都不属于这次交付。
