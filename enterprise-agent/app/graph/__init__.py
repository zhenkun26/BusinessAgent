"""LangGraph 图编排模块(W5 实现)

对应 v3 方案 6.3 节:
- StateGraph: 状态机建模业务流程
- Send API: 并行 fan-out 子 Agent
- interrupt: 人机协同(审批等)
- Checkpointer: 断点恢复(W8 接入 Redis)
"""
