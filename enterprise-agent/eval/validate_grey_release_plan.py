"""校验灰度发布方案的结构、指标和回滚路径，不执行真实放量。"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXPECTED_STAGE_IDS = ("G0", "G1", "G2", "G3")
_STAGE_ROW_RE = re.compile(r"^\|\s*(G[0-3])\s*\|")
_EXPECTED_METRICS = ("可用性", "p95", "p99", "错误率", "RTO", "RPO")
_ROLLBACK_TERMS = ("P0/P1", "错误率", "p95", "权限越界", "备份不可用")


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


def _section(markdown: str, start: str, end: str) -> str:
    start_index = markdown.find(start)
    if start_index < 0:
        return ""
    end_index = markdown.find(end, start_index + len(start))
    return markdown[start_index:] if end_index < 0 else markdown[start_index:end_index]


def _rows(section: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in section.splitlines():
        if _STAGE_ROW_RE.match(line):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def validate_grey_release_plan(plan_path: Path) -> dict[str, Any]:
    markdown = plan_path.read_text(encoding="utf-8")
    strategy = _section(markdown, "## 1. 灰度策略", "## 2. 观察指标")
    metrics = _section(markdown, "## 2. 观察指标", "## 3. 回滚触发条件")
    triggers = _section(markdown, "## 3. 回滚触发条件", "## 4. 回滚路径")
    rollback = _section(markdown, "## 4. 回滚路径", "## 5. 全量上线门槛检查单")
    stage_rows = _rows(strategy)
    stage_ids = [row[0] for row in stage_rows]
    stages_complete = (
        sorted(stage_ids) == sorted(EXPECTED_STAGE_IDS)
        and len(stage_ids) == len(set(stage_ids))
        and all(len(row) >= 4 for row in stage_rows)
    )
    stage_ordered = stage_ids == list(EXPECTED_STAGE_IDS)
    strategy_has_observation_window = "总观察期" in strategy and (
        "2-4 周" in strategy or "4 周" in strategy
    )
    duration_is_bounded = "G3" in strategy and "2 周以上" not in strategy
    metrics_complete = all(term in metrics for term in _EXPECTED_METRICS)
    rollback_triggers_complete = all(term in triggers for term in _ROLLBACK_TERMS)
    rollback_path_complete = all(
        term in rollback for term in ("停止新增用户", "关闭对应 provider", "上一稳定镜像", "/health", "/ready")
    ) and len(re.findall(r"^\d+\.\s", rollback, flags=re.MULTILINE)) >= 7
    no_release_claim = "不代表项目已经全量上线" in markdown and "不允许全量放行" in markdown
    owner_confirmation_pending = "产品负责人" in markdown and "正式阈值需要产品负责人" in markdown

    checks = [
        Check(
            "stage_ids_complete",
            stages_complete,
            f"灰度阶段 {len(stage_ids)} 个，期望 G0/G1/G2/G3 且编号不重复",
        ),
        Check(
            "stage_order_and_columns",
            stage_ordered and stages_complete,
            "阶段按 G0 → G1 → G2 → G3 排列且包含范围、观察期、放量前提",
        ),
        Check(
            "observation_window_is_declared",
            strategy_has_observation_window,
            "方案声明总观察期边界",
        ),
        Check(
            "observation_window_is_bounded",
            duration_is_bounded,
            "各阶段观察期与总观察期口径一致，未出现无上限的阶段",
        ),
        Check(
            "sla_metrics_are_referenced",
            metrics_complete,
            "可用性、p95、p99、错误率、RTO、RPO 均有观察口径",
        ),
        Check(
            "rollback_trigger_and_path_are_actionable",
            rollback_triggers_complete and rollback_path_complete,
            "回滚触发条件覆盖安全/SLA/数据风险，且路径包含停止、回退、健康检查步骤",
        ),
        Check(
            "plan_does_not_claim_release",
            no_release_claim,
            "灰度方案明确不等于全量放行",
        ),
    ]
    structural_pass = all(check.passed for check in checks[:3] + checks[4:])
    needs_revision = not checks[3].passed
    overall_status = "needs_revision" if structural_pass and needs_revision else (
        "passed" if structural_pass else "invalid"
    )
    plan_approval = overall_status == "passed" and not owner_confirmation_pending
    review_conclusion = (
        "approved"
        if overall_status == "passed" and not owner_confirmation_pending
        else "conditional"
        if overall_status == "passed"
        else "blocked"
    )
    conclusion = (
        "方案结构、指标和回滚路径完整，可进入负责人评审。"
        if overall_status == "passed" and not owner_confirmation_pending
        else "方案结构、指标和回滚路径完整，观察期口径已统一；业务观察阈值仍需产品负责人确认，不能据此开始真实灰度。"
        if overall_status == "passed"
        else "方案结构基本完整，但 G3 使用‘2 周以上’导致总观察期没有明确上限；3.2 不通过，需先统一观察期口径。"
        if overall_status == "needs_revision"
        else "方案结构或关键回滚证据不完整，不能进入灰度评审。"
    )
    return {
        "plan": str(plan_path),
        "overall_status": overall_status,
        "plan_approval": plan_approval,
        "review_conclusion": review_conclusion,
        "execution_ready": False,
        "release_evidence": False,
        "conclusion": conclusion,
        "owner_confirmation_pending": owner_confirmation_pending,
        "checks": [check.as_dict() for check in checks],
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# 灰度方案评审记录",
        "",
        f"- overall_status: `{report['overall_status']}`",
        f"- plan_approval: `{str(report['plan_approval']).lower()}`",
        f"- review_conclusion: `{report['review_conclusion']}`",
        f"- execution_ready: `{str(report['execution_ready']).lower()}`",
        f"- release_evidence: `{str(report['release_evidence']).lower()}`",
        "",
        f"> {report['conclusion']}",
        "",
        "| 检查项 | 结果 | 说明 |",
        "|---|---|---|",
    ]
    for check in report["checks"]:
        status = "✅ passed" if check["passed"] else "❌ failed"
        lines.append(f"| {check['name']} | {status} | {check['detail']} |")
    lines.extend(
        [
            "",
            "> 本记录只评审方案可执行性，不代表真实 UAT、灰度执行或全量放行已经完成。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="校验灰度发布方案")
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("../docs/30-guides/发布灰度与上线门槛检查单.md"),
    )
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    report = validate_grey_release_plan(args.plan)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(serialized, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(_markdown_report(report), encoding="utf-8")
    print(serialized, end="")
    return 0 if report["overall_status"] != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
