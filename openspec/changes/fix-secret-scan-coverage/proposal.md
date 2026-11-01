# 修复合并事件秘密扫描零覆盖

main 合并 PR #4 后，现有 action 的 first-parent 与 no-merges 组合使实际扫描提交数为零，步骤却成功。本变更仅修复事件范围、最终树覆盖和失败传播；不改秘密规则，不引入 PR #5 的指纹例外，不调整业务或部署。

push 依据事件 before/after，PR 依据 base 与实际合成 merge，manual 仅检查选中提交祖先；拒绝缺对象、错 checkout、空范围与未支持事件。增加真实 Git 历史和合成秘密回归及独立安全审核。
