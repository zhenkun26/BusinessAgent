"""核对发布灰度与上线门槛检查单，不执行发布或改变任何运行状态。"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXPECTED_GATE_IDS = (
    "GATE-01",
    "GATE-02",
    "GATE-03",
    "GATE-04",
    "GATE-05",
    "GATE-06",
)
_GATE_ROW_RE = re.compile(r"^\|\s*(GATE-\d{2})\s*\|")
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_REPO_PATH_PREFIXES = ("docs/", "enterprise-agent/", "openspec/", "interview/")
_NON_VERSIONED_EVIDENCE_PREFIXES = (
    "eval/results/",
    "enterprise-agent/eval/results/",
)


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
        if not _GATE_ROW_RE.match(line):
            continue
        result.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return result


def _is_gate_ready(status: str) -> bool:
    normalized = status.replace(" ", "")
    if any(marker in normalized for marker in ("待", "未", "部分", "缺", "阻止")):
        return False
    return any(marker in normalized for marker in ("已有证据", "已通过", "全部满足", "已完成"))


def _referenced_paths(evidence: str) -> list[str]:
    return [
        path
        for path in _BACKTICK_RE.findall(evidence)
        if path.startswith(_REPO_PATH_PREFIXES) and not path.endswith("/")
    ]


def _is_non_versioned_evidence_path(path: str) -> bool:
    """运行时评测产物按版本控制规范被忽略，不要求出现在 CI checkout。"""

    return path.startswith(_NON_VERSIONED_EVIDENCE_PREFIXES)


def validate_release_gate(checklist_path: Path, project_root: Path) -> dict[str, Any]:
    markdown = checklist_path.read_text(encoding="utf-8")
    rows = _rows(_section(markdown, "## 5. 全量上线门槛检查单", "## 6. 灰度记录模板"))
    row_ids = [row[0] for row in rows]
    rows_have_columns = all(len(row) >= 4 for row in rows)
    gate_results: list[dict[str, Any]] = []

    for row in rows:
        gate_id = row[0]
        evidence = row[2] if len(row) >= 3 else ""
        status = row[3] if len(row) >= 4 else ""
        paths = _referenced_paths(evidence)
        missing_paths = [
            path
            for path in paths
            if not _is_non_versioned_evidence_path(path)
            and not (project_root / path).exists()
        ]
        gate_results.append(
            {
                "gate_id": gate_id,
                "gate": row[1] if len(row) >= 2 else "",
                "evidence": evidence,
                "current_status": status,
                "ready": _is_gate_ready(status),
                "referenced_paths": paths,
                "missing_paths": missing_paths,
            }
        )

    ids_complete = sorted(row_ids) == sorted(EXPECTED_GATE_IDS) and len(row_ids) == len(
        set(row_ids)
    )
    evidence_complete = rows_have_columns and all(
        result["evidence"] for result in gate_results
    )
    missing_paths: list[str] = []
    for result in gate_results:
        missing_paths.extend(result["missing_paths"])
    paths_exist = not missing_paths
    ready_gate_ids = [result["gate_id"] for result in gate_results if result["ready"]]
    blocked_gate_ids = [result["gate_id"] for result in gate_results if not result["ready"]]
    all_gates_ready = ids_complete and rows_have_columns and all(
        result["ready"] for result in gate_results
    )
    blocked_declared = "BLOCKED" in markdown and "不允许全量放行" in markdown
    release_allowed = all_gates_ready and not blocked_declared
    formal_release = release_allowed and "放行结论：批准" in markdown
    checks = [
        Check(
            "gate_ids_complete",
            ids_complete,
            f"检查单包含 {len(row_ids)} 行，期望 {len(EXPECTED_GATE_IDS)} 行且编号不重复",
        ),
        Check(
            "gate_rows_have_required_columns",
            rows_have_columns,
            "每个门槛均包含编号、门槛、证据和当前状态四列",
        ),
        Check(
            "evidence_cells_are_present",
            evidence_complete,
            "每个门槛均填写前置证据引用",
        ),
        Check(
            "referenced_paths_exist",
            paths_exist,
            "仓库内可解析的证据路径均存在"
            if paths_exist
            else f"缺失路径：{', '.join(sorted(set(missing_paths)))}",
        ),
        Check(
            "blocked_state_is_declared",
            blocked_declared if blocked_gate_ids else True,
            "存在未就绪门槛时，检查单明确声明 BLOCKED"
            if blocked_gate_ids
            else "全部门槛就绪，无需 BLOCKED 声明",
        ),
        Check(
            "missing_gate_blocks_release",
            (not blocked_gate_ids) or not release_allowed,
            f"未就绪门槛：{', '.join(blocked_gate_ids) or '无'}",
        ),
    ]
    structure_valid = all(check.passed for check in checks[:4])
    overall_status = "invalid" if not structure_valid else ("ready" if release_allowed else "blocked")
    conclusion = (
        "六项门槛证据齐备，但仍需正式签署放行结论。"
        if release_allowed and not formal_release
        else "六项门槛均满足且检查单未声明阻断，可进入正式放行评审。"
        if formal_release
        else f"当前保持 BLOCKED；未就绪门槛：{', '.join(blocked_gate_ids) or '检查单结构无效'}。"
    )
    return {
        "checklist": str(checklist_path),
        "overall_status": overall_status,
        "release_allowed": release_allowed,
        "formal_release": formal_release,
        "release_evidence": all_gates_ready,
        "ready_gate_ids": ready_gate_ids,
        "blocked_gate_ids": blocked_gate_ids,
        "conclusion": conclusion,
        "gates": gate_results,
        "checks": [check.as_dict() for check in checks],
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# 发布门槛核对报告",
        "",
        f"- overall_status: `{report['overall_status']}`",
        f"- release_allowed: `{str(report['release_allowed']).lower()}`",
        f"- formal_release: `{str(report['formal_release']).lower()}`",
        f"- release_evidence: `{str(report['release_evidence']).lower()}`",
        f"- ready_gate_ids: `{', '.join(report['ready_gate_ids']) or 'none'}`",
        f"- blocked_gate_ids: `{', '.join(report['blocked_gate_ids']) or 'none'}`",
        "",
        f"> {report['conclusion']}",
        "",
        "## 门槛明细",
        "",
        "| 编号 | 当前状态 | 核对结果 | 缺失路径 |",
        "|---|---|---|---|",
    ]
    for gate in report["gates"]:
        result = "✅ ready" if gate["ready"] else "❌ blocked"
        missing = ", ".join(gate["missing_paths"]) or "—"
        lines.append(
            f"| {gate['gate_id']} | {gate['current_status']} | {result} | {missing} |"
        )
    lines.extend(["", "## 核对器自检", "", "| 检查项 | 结果 | 说明 |", "|---|---|---|"])
    for check in report["checks"]:
        status = "✅ passed" if check["passed"] else "❌ failed"
        lines.append(f"| {check['name']} | {status} | {check['detail']} |")
    lines.extend(
        [
            "",
            "> 本报告只证明检查单已被程序化核对，不替代真实 UAT、安全测试、灰度观察或负责人签署。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="核对发布灰度与上线门槛检查单")
    parser.add_argument(
        "--checklist",
        type=Path,
        default=Path("../docs/30-guides/发布灰度与上线门槛检查单.md"),
    )
    parser.add_argument("--project-root", type=Path, default=Path(".."))
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    report = validate_release_gate(args.checklist, args.project_root)
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
