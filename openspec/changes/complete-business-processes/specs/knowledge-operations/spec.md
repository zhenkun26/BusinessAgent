## Purpose

为知识文档补齐从录入、反馈候选、人工审核到激活的运营生命周期，并让检索降级链在向量库故障时仍能通过 PostgreSQL 全文检索返回受控结果。

## ADDED Requirements

### Requirement: 文档入库必须写入文档台账

系统在知识文档成功入库时 SHALL 将文档元数据写入 `documents` 表，状态为 `active`，并记录命名空间、可见角色、文档类型与上传者；同一 `document_id` 重复入库时 SHALL 采用幂等更新，不得产生重复的 `active` 记录。

#### Scenario: 文档成功入库后出现在台账中
- **WHEN** 管理员通过入库流程导入一份新文档且向量写入成功
- **THEN** 该文档以 `active` 状态出现在文档台账中，且可被对应角色的检索请求命中

#### Scenario: 重复导入同一文档
- **WHEN** 同一 `document_id` 的文档再次入库
- **THEN** 文档台账更新为最新内容且不产生重复的 `active` 记录

### Requirement: 用户反馈候选必须经审核后才能激活

系统 SHALL 将带评论的知识点踩反馈持久化为 `draft` 状态的知识候选；只有管理员审核通过后 SHALL 才进入向量库并变为 `active`，审核拒绝的候选 SHALL 保持不可检索并记录审核人与时间。

#### Scenario: 查看待审核候选
- **WHEN** 存在 `draft` 状态的知识候选且管理员请求候选列表
- **THEN** 返回候选标题、评论内容、来源会话与提交用户

#### Scenario: 审核通过候选
- **WHEN** 管理员批准某个知识候选
- **THEN** 候选状态变为 `active`，内容进入向量库，并可被检索命中

#### Scenario: 审核拒绝候选
- **WHEN** 管理员拒绝某个知识候选
- **THEN** 候选状态变为 `rejected`，内容不进入向量库，且审核人、拒绝时间被记录

### Requirement: 检索降级链必须包含 PostgreSQL 全文检索

当向量检索与 Milvus 关键词扫描都不可用或返回空时，系统 SHALL 通过 PostgreSQL 全文/模糊检索返回结果，并在该降级路径上强制应用角色权限与部门命名空间过滤。

#### Scenario: 向量库不可用时降级到 PostgreSQL
- **WHEN** Milvus 不可用且用户发起知识问答
- **THEN** 检索在降级链上命中 PostgreSQL 全文检索并返回带命名空间的结果，响应中标记降级阶段

#### Scenario: 降级路径保持命名空间隔离
- **WHEN** 客服用户通过降级路径检索销售部专属文档
- **THEN** 结果中不包含销售部命名空间文档

### Requirement: 前端知识库文档必须展示真实台账

系统 SHALL 向前端提供真实文档台账接口，前端知识库文档页 SHALL 展示接口返回的状态、命名空间与上传者，不得使用写死的 Mock 数据。

#### Scenario: 前端加载知识库文档
- **WHEN** 用户打开知识库文档页
- **THEN** 页面展示来自文档台账接口的数据，且包含 `draft`、`active`、`rejected` 等真实状态
