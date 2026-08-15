# UAT 技术彩排模拟数据

`fixture.json` 是 G0 技术彩排用的合成数据，不是正式 UAT 数据，也不是数据库导入脚本。

## 生成与校验

在 `enterprise-agent/` 目录执行：

```bash
python eval/generate_uat_simulation.py
python eval/generate_uat_simulation.py --check
python eval/run_uat_replay.py
```

默认使用固定 seed `20260815`，因此可以复现同一批数据。需要生成另一批可复现数据时传入 `--seed` 和新的输出路径：

```bash
python eval/generate_uat_simulation.py \
  --seed 20260816 \
  --output eval/uat_simulation/fixture-20260816.json
```

数据覆盖 11 个模拟用户、12 个客户、24 个订单、12 个工单、8 个知识文档、6 个会话、8 个审批和 12 个 UAT 场景。所有实体都带有合成数据标记；脚本不会连接 PostgreSQL、Milvus、Redis、CRM、邮件或工单系统。

使用时必须保持 `official_uat=false`、`external_side_effects_allowed=false`。在没有产品负责人确认和独立 UAT 环境前，不得直接导入数据库或使用生产凭证。

回放器默认生成：

- `enterprise-agent/eval/results/uat_replay_report.json`
- `enterprise-agent/eval/results/uat_replay_report.md`

回放器只做结构和安全契约检查，不执行 API、数据库或外部系统动作。报告中的 `formal_uat=false`、`release_evidence=false` 必须保持不变；回放通过也只表示 G0 技术彩排通过。
