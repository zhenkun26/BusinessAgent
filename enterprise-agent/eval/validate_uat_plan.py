"""校验 UAT 计划与 G0 fixture 的结构一致性。

该脚本只检查计划完整性，不执行 UAT、不连接业务系统，也不把 G0 结果升级为正式证据。
"""

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
_SCENARIO_ID_RE = re.compile(r"^\|\s*(UAT-[A-Z0-9]+)\s*\|")


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
    result: list[list[str]] = []
    for line in section.splitlines():
        match = _SCENARIO_ID_RE.match(line)
        if not match:
            continue
        result.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return result


def validate_uat_plan(plan_path: Path, fixture_path: Path) -> dict[str, Any]:
    markdown = plan_path.read_text(encoding="utf-8")
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    matrix = _rows(_section(markdown, "## 4. UAT 场景矩阵", "## 5. 场景通过标准"))
    execution = _rows(_section(markdown, "## 6. 执行记录模板", "## 7. 当前结论"))
    fixture_ids = [str(item.get("scenario_id")) for item in fixture.get("scenarios", [])]

    checks = [
        Check(
            "scenario_ids_match_fixture",
            sorted(fixture_ids) == sorted(EXPECTED_SCENARIO_IDS),
            f"fixture={len(fixture_ids)} expected={len(EXPECTED_SCENARIO_IDS)}",
        ),
        Check(
            "matrix_covers_each_scenario_once",
            sorted(row[0] for row in matrix) == sorted(EXPECTED_SCENARIO_IDS)
            and len(matrix) == len(set(row[0] for row in matrix)),
            f"matrix_rows={len(matrix)}",
        ),
        Check(
            "matrix_has_action_and_pass_standard",
            all(len(row) >= 6 and row[4] and row[5] for row in matrix)
            and len(matrix) == len(EXPECTED_SCENARIO_IDS),
            "每个场景均有最小验收动作和通过标准",
        ),
        Check(
            "execution_template_covers_each_scenario_once",
            sorted(row[0] for row in execution) == sorted(EXPECTED_SCENARIO_IDS)
            and len(execution) == len(set(row[0] for row in execution)),
            f"execution_rows={len(execution)}",
        ),
        Check(
            "execution_is_not_marked_as_completed",
            all(len(row) >= 5 and row[4] == "待执行" for row in execution),
            "模板未把空白执行记录误标为通过",
        ),
        Check(
            "g0_fixture_is_not_formal_uat",
            fixture.get("official_uat") is False
            and fixture.get("external_side_effects_allowed") is False,
            "G0 安全标记保持 official_uat=false 且 external_side_effects_allowed=false",
        ),
        Check(
            "plan_declares_real_resource_blockers",
            all(term in markdown for term in ("真实验收用户", "验收环境", "验收窗口", "结果签署人")),
            "计划明确列出真实 UAT 资源待确认项",
        ),
    ]
    passed = all(check.passed for check in checks)
    return {
        "plan": str(plan_path),
        "fixture": str(fixture_path),
        "overall_status": "passed" if passed else "failed",
        "formal_uat": False,
        "release_evidence": False,
        "execution_ready": False,
        "conclusion": (
            "计划结构与 G0 fixture 一致，但真实用户、独立环境、排期和签署人未确认；"
            "不得放行正式 UAT。"
        ),
        "checks": [check.as_dict() for check in checks],
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# UAT 计划结构评审报告",
        "",
        f"- overall_status: `{report['overall_status']}`",
        f"- formal_uat: `{str(report['formal_uat']).lower()}`",
        f"- release_evidence: `{str(report['release_evidence']).lower()}`",
        f"- execution_ready: `{str(report['execution_ready']).lower()}`",
        "",
        f"> {report['conclusion']}",
        "",
        "| 检查项 | 结果 | 说明 |",
        "|---|---|---|",
    ]
    for check in report["checks"]:
        status = "✅ passed" if check["passed"] else "❌ failed"
        lines.append(f"| {check['name']} | {status} | {check['detail']} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 UAT 计划与 G0 fixture 的结构一致性")
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("../docs/30-guides/UAT验收计划.md"),
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("eval/uat_simulation/fixture.json"),
    )
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    report = validate_uat_plan(args.plan, args.fixture)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(serialized, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(_markdown_report(report), encoding="utf-8")
    print(serialized, end="")
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
