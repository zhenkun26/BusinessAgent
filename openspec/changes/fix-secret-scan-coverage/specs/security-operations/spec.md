## ADDED Requirements

### Requirement: CI秘密扫描必须覆盖事件引入的历史与最终树

系统 SHALL 验证事件提交身份，选择非空且可解析的事件范围，遍历其全部相关父链并检查合并差异与精确最终tracked树；不得盲目扫描无关refs，不得用候选PR新增豁免覆盖base策略。

#### Scenario: 合并包含后被删除的分支秘密
- **WHEN** push merge 第二父链曾提交秘密后删除
- **THEN** 历史扫描仍失败，不因最终树无秘密而通过

#### Scenario: 合并解决内容新增秘密
- **WHEN** 秘密只在merge结果出现
- **THEN** merge差异或最终树扫描阻断

#### Scenario: 范围或工具失效
- **WHEN** 提交缺失、checkout不符、范围为空、扫描工具出错或报告无效
- **THEN** CI失败，不能表述为零发现
