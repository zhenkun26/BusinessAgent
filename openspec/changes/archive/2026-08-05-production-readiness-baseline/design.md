## Context

现状见 proposal.md 的 Why。关键约束：项目为单机 Docker Compose 部署（docker-compose.prod.yml），备份为每日 pg_dump + etcd snapshot 的文档脚本（deploy/DEPLOY.md:199-243），尚无恢复演练记录；RAG 评测平均延迟 1049ms（eval/results/latest.json）；审批与审计能力已存在（approval-lifecycle 规格，外部邮件工具 `requires_approval=True`）；文档体系遵循六大层规范，ROADMAP/DECISIONS/ISSUES 各为单一事实源。

## Goals / Non-Goals

**Goals:**
- 把系统边界、SLA、风险操作清单冻结为正式规格，可被后续压测、UAT、灰度 change 直接引用。
- 数据/权限梳理与架构评审结论落入既有单一事实源（产品文档、DECISIONS.md），不新建平行文档体系。

**Non-Goals:**
- 不改动任何业务代码与部署配置。
- 不在本 change 中做压测、演练或真实系统接入（后续 change 承接）。
- SLA 目标值本轮定为初值，不追求一次到位（待 load-test-and-dr-drill 压测后校准）。

## Decisions

### 1. 三类契约合并为一个 `production-readiness` 规格，而非三个规格

系统边界、SLA、风险操作清单同属"上线决策基线"，生命周期一致（评审冻结 → 验收引用 → 变更再评审），合并为一个规格可减少交叉引用成本。

备选：拆成三个独立规格。否决：三者互相引用（如 SLA 达标线服务于风险操作的放行判断），拆开只会增加同步负担。

### 2. SLA 初值按单机 Compose 现实设定，压测后校准

初值：可用性 ≥ 99.5%（单机现实上限，K8s 后再提升）；核心接口 p95 ≤ 2s、p99 ≤ 5s（对话类接口以首 token 计，当前 RAG 平均 1049ms 为参照）；错误率 < 0.5%；RTO ≤ 1 小时、RPO ≤ 24 小时（对齐每日备份频率）。度量口径：以 Prometheus/Nginx 日志为数据来源。

备选：直接对标互联网标准 99.9%。否决：单机 Compose 架构无法支撑，写进规格只会成为无法兑现的承诺（评审原话："保证稳定不能靠承诺"）。

### 3. 风险操作清单以现有工具与 API 全集为基线盘点

从 `app/tools/`（CRM/邮件/工单 6 个工具）与 admin API 逐一盘点，首批必含：对外发送邮件（已有 `requires_approval`）、批量数据变更、删除类操作、用户创建/禁用/角色调整。清单正文维护在规格中，产品文档附录引用，审批流转规则继续由 `approval-lifecycle` 规格承载，本规格只约束"清单内操作必须审批 + 审计"。

备选：把审批流转细节也搬进本规格。否决：违反单一事实源原则，approval-lifecycle 已有完整状态机。

### 4. 评审结论落 DECISIONS.md，规格归档后即冻结

数据/权限梳理与架构评审以评审会形式进行，结论按既有格式追加到 `docs/40-process/DECISIONS.md`（背景/决策/放弃/改判条件）；本 change 归档后规格即冻结，后续变更需新开 change。

## Risks / Trade-offs

- SLA 初值可能偏松或偏紧 → 明确标注为初值，`load-test-and-dr-drill` 压测后必须回访校准，校准动作写入该 change 的 tasks。
- 风险操作清单盘点可能遗漏 → 评审环节增加"对照工具注册表与 API 路由表逐一核对"的机械步骤，降低纯人工判断的遗漏率。
- 纯文档 change 容易流于形式 → tasks 中每个交付物都有明确验收方式（规格可 validate、清单与路由表对照、DECISIONS 条目编号可查）。

## Migration Plan

无代码迁移。执行顺序：盘点现状（工具/API/数据/权限）→ 起草三类契约 → 架构评审 → 结论落 DECISIONS 与产品文档 → 归档冻结。

## Open Questions

- 风险操作清单中"批量数据变更"的阈值如何定义（多少条以上算批量）？评审时按现有工具实际参数确定。
- 可用性目标是否要为 Milvus/Ollama 等本地依赖单独定义降级口径（如向量库故障时 PG 降级检索是否计入可用）？倾向计入但标注降级状态，评审确认。
