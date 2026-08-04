## Purpose

为公共接口建立可持续运行的单元测试体系：覆盖正常、边界与错误路径，Mock 外部依赖，保证测试快速、自包含、可离线运行。

## ADDED Requirements

### Requirement: 公共接口必须有单元测试

系统 SHALL 为每个公共接口（API 端点、Agent 公共方法、工具 `invoke`、RAG 检索入口、图节点）提供单元测试，覆盖正常路径、边界条件与错误路径。

#### Scenario: 测试套件覆盖正常路径
- **WHEN** 运行测试套件
- **THEN** 每个公共接口至少有一个正常路径测试并通过

#### Scenario: 测试套件覆盖错误路径
- **WHEN** 输入非法、权限不足或外部依赖失败
- **THEN** 对应错误路径测试通过，且不依赖真实外部服务

### Requirement: 测试必须 Mock 外部依赖

系统 SHALL 在测试中通过 Mock/Fake 替代数据库、网络、LLM、文件系统与消息队列，测试套件 SHALL 可在无 Docker、无外部服务、无网络环境下运行。

#### Scenario: 离线环境运行测试
- **WHEN** 在未启动 Docker 与外部服务的环境中运行 `pytest`
- **THEN** 测试全部通过且不发起真实网络请求

### Requirement: 测试命名必须遵循项目约定

测试函数 SHALL 使用 `test_should_<expected_behaviour>_when_<condition>` 命名，并采用 Given-When-Then 结构组织断言。

#### Scenario: 命名检查
- **WHEN** 代码评审检查新增测试函数名
- **THEN** 所有测试函数名满足 `test_should_<behaviour>_when_<condition>` 格式

### Requirement: 测试必须可度量覆盖率

系统 SHALL 提供覆盖率统计入口，使开发者在本地运行测试后能看到行覆盖率报告。

#### Scenario: 生成覆盖率报告
- **WHEN** 开发者以覆盖率模式运行测试
- **THEN** 输出各模块行覆盖率与总体覆盖率
