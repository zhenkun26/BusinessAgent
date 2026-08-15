"""核对 UAT 是否具备真实执行条件，不执行真实 UAT 或外部副作用。"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXPECTED_SCENARIO_IDS = (
    "UAT-K01",
    "UAT-K02",
    "UAT-A01",
    "UAT-A02",
    "UAT-E01",
    "UAT-E02",
    "UAT-P01",
    "UAT-P02",
    "UAT-C01",
    "UAT-C02",
    "UAT-C03",
    "UAT-O01",
)
EXPECTED_RESOURCES = ("真实验收用户", "验收环境", "验收窗口", "外部系统范围", "结果签署人")
_RESOURCE_ROW_RE = re.compile(r"^\|\s*(真实验收用户|验收环境|验收窗口|外部系统范围|结果签署人)\s*\|")
_SCENARIO_ROW_RE = re.compile(r"^\|\s*(UAT-[A-Z0-9]+)\s*\|")
_PLACEHOLDER_TERMS = ("待定", "待填", "待确认", "待执行")


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


def _rows(section: str, pattern: re.Pattern[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in section.splitlines():
        if pattern.match(line):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def validate_uat_execution_readiness(plan_path: Path) -> dict[str, Any]:
    markdown = plan_path.read_text(encoding="utf-8")
    resource_rows = _rows(
        _section(markdown, "### 2.2 待确认资源", "### 2.3 G0 技术彩排数据"),
        _RESOURCE_ROW_RE,
    )
    execution_rows = _rows(
        _section(markdown, "## 6. 执行记录模板", "## 7. 当前结论"),
        _SCENARIO_ROW_RE,
    )
    resource_map = {row[0]: row for row in resource_rows if row}
    unresolved_resources = [
        resource
        for resource in EXPECTED_RESOURCES
        if resource not in resource_map
        or len(resource_map[resource]) < 3
        or any(term in resource_map[resource][1] for term in _PLACEHOLDER_TERMS)
    ]
    execution_ids = [row[0] for row in execution_rows]
    execution_template_intact = (
        sorted(execution_ids) == sorted(EXPECTED_SCENARIO_IDS)
        and len(execution_ids) == len(set(execution_ids))
        and all(len(row) >= 5 and row[4] == "待执行" for row in execution_rows)
    )
    independent_environment = (
        "验收环境" in resource_map
        and len(resource_map["验收环境"]) >= 3
        and "独立" in resource_map["验收环境"][2]
        and not any(term in resource_map["验收环境"][1] for term in _PLACEHOLDER_TERMS)
    )
    no_formal_claim = (
        "不代表 UAT 已完成" in markdown
        and "formal_uat=false" in markdown
        and "不得因为本文建立而关闭" in markdown
    )
    checks = [
        Check(
            "resource_rows_complete",
            not unresolved_resources,
            "五类真实执行资源均已填写"
            if not unresolved_resources
            else f"待确认资源：{', '.join(unresolved_resources)}",
        ),
        Check(
            "independent_uat_environment",
            independent_environment,
            "验收环境已确认且为独立环境"
            if independent_environment
            else "验收环境仍未确认独立性",
        ),
        Check(
            "execution_template_is_untouched",
            execution_template_intact,
            "12 个场景均保留待执行状态，未伪造正式结果"
            if execution_template_intact
            else "执行记录模板缺行、重复或已被误标记",
        ),
        Check(
            "formal_uat_boundary_is_declared",
            no_formal_claim,
            "计划明确 G0 彩排不能替代正式 UAT",
        ),
    ]
    structure_valid = all(check.passed for check in checks[2:])
    execution_ready = structure_valid and not unresolved_resources and independent_environment
    overall_status = "ready" if execution_ready else "blocked" if structure_valid else "invalid"
    return {
        "plan": str(plan_path),
        "overall_status": overall_status,
        "execution_ready": execution_ready,
        "formal_uat": False,
        "release_evidence": False,
        "unresolved_resources": unresolved_resources,
        "conclusion": (
            "真实 UAT 资源、独立环境与排期已齐备，可进入正式执行。"
            if execution_ready
            else "正式 UAT 仍被真实用户、独立环境或排期/签署资源阻断；G0 彩排不计入正式证据。"
        ),
        "checks": [check.as_dict() for check in checks],
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# UAT 执行准备核对报告",
        "",
        f"- overall_status: `{report['overall_status']}`",
        f"- execution_ready: `{str(report['execution_ready']).lower()}`",
        f"- formal_uat: `{str(report['formal_uat']).lower()}`",
        f"- release_evidence: `{str(report['release_evidence']).lower()}`",
        f"- unresolved_resources: `{', '.join(report['unresolved_resources']) or 'none'}`",
        "",
        f"> {report['conclusion']}",
        "",
        "| 检查项 | 结果 | 说明 |",
        "|---|---|---|",
    ]
    for check in report["checks"]:
        status = "✅ passed" if check["passed"] else "❌ blocked"
        lines.append(f"| {check['name']} | {status} | {check['detail']} |")
    lines.extend(
        [
            "",
            "> 本报告只核对执行准备度，不执行真实用户验收、不连接外部系统，也不关闭 I-02。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="核对 UAT 执行准备度")
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("../docs/30-guides/UAT验收计划.md"),
    )
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    report = validate_uat_execution_readiness(args.plan)
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
