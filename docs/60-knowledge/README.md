# 60-knowledge · 知识数据库层

本层为知识库数据的索引层。知识文档数据保留在 `enterprise-agent/eval/sample_docs/`（单一事实源），此处提供导航与入库规范摘要。

## 数据索引

| 文档 | 命名空间 | 说明 |
|---|---|---|
| [销售政策.md](../../enterprise-agent/eval/sample_docs/销售政策.md) | shared_company | 客户跟进 / 折扣政策 |
| [产品手册.md](../../enterprise-agent/eval/sample_docs/产品手册.md) | shared_company | 产品版本与定价 |
| [售后服务政策.md](../../enterprise-agent/eval/sample_docs/售后服务政策.md) | shared_company | 服务承诺与响应时间 |
| [常见问题FAQ.md](../../enterprise-agent/eval/sample_docs/常见问题FAQ.md) | shared_company | 账号权限等常见问题 |
| [财务报销制度.md](../../enterprise-agent/eval/sample_docs/财务报销制度.md) | shared_company | 报销流程 |
| [销售部内部激励方案.md](../../enterprise-agent/eval/sample_docs/dept_sales/销售部内部激励方案.md) | dept_sales | 部门专属（仅销售部与管理层） |
| [财务部预算审批细则.md](../../enterprise-agent/eval/sample_docs/dept_finance/财务部预算审批细则.md) | dept_finance | 部门专属（仅财务部与管理层） |

## 入库规范摘要

```bash
# 公司共享文档（所有人可见）
python -m app.rag.ingest <文件或目录> --type policy --ns shared_company

# 部门专属文档（必须显式指定角色，否则默认全角色可见！）
python -m app.rag.ingest <文件> --type policy --ns dept_sales --roles salesperson manager admin
```

详细入库/重置操作见 [运维维护手册](../30-guides/运维维护手册.md) 第 3.1 节。
