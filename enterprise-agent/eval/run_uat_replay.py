"""回放 G0 UAT 技术彩排 fixture。

该脚本只读取 JSON fixture 并生成报告，不启动应用、不连接数据库，也不调用外部系统。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_FIXTURE = Path(__file__).parent / "uat_simulation" / "fixture.json"
DEFAULT_RESULT_DIR = Path(__file__).parent / "results"
DEFAULT_JSON_REPORT = DEFAULT_RESULT_DIR / "uat_replay_report.json"
DEFAULT_MARKDOWN_REPORT = DEFAULT_RESULT_DIR / "uat_replay_report.md"

EXPECTED_ROLES = {"salesperson", "customer_service", "finance", "manager", "admin"}
EXPECTED_NAMESPACES = {"dept_sales", "dept_cs", "dept_finance", "dept_hr", "shared_company"}
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
REQUIRED_APPROVAL_STATUSES = {
    "pending",
    "rejected",
    "approved_pending_reauth",
    "executed",
    "timeout",
}
ALLOWED_SESSION_STATUSES = {"pending", "running", "completed", "failed"}
ALLOWED_APPROVAL_STATUSES = REQUIRED_APPROVAL_STATUSES | {"approved"}
SAFE_EMAIL_DOMAINS = {"example.invalid", "company.internal"}


def _records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [record for record in value if isinstance(record, dict)]


def _index_records(
    records: Iterable[dict[str, Any]], key: str
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    index: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for record in records:
        record_id = record.get(key)
        if not isinstance(record_id, str):
            continue
        if record_id in index:
            duplicates.append(record_id)
        index[record_id] = record
    return index, duplicates


def _check(
    check_id: str,
    passed: bool,
    message: str,
    details: list[str] | None = None,
    *,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "scenario_id": scenario_id,
        "status": "passed" if passed else "failed",
        "message": message,
        "details": details or [],
    }


def _collect_references(fixture: dict[str, Any]) -> tuple[set[str], list[str]]:
    known_ids: set[str] = set()
    duplicate_ids: list[str] = []
    collections = (
        ("users", "user_id"),
        ("customers", "customer_id"),
        ("orders", "order_id"),
        ("tickets", "ticket_id"),
        ("documents", "document_id"),
        ("sessions", "session_id"),
        ("approvals", "approval_id"),
    )
    for collection_name, id_key in collections:
        index, duplicates = _index_records(_records(fixture.get(collection_name)), id_key)
        known_ids.update(index)
        duplicate_ids.extend(f"{collection_name}:{item}" for item in duplicates)
    return known_ids, duplicate_ids


def _check_safety_markers(fixture: dict[str, Any]) -> dict[str, Any]:
    details: list[str] = []
    if fixture.get("official_uat") is not False:
        details.append("official_uat 必须严格为 false")
    if fixture.get("external_side_effects_allowed") is not False:
        details.append("external_side_effects_allowed 必须严格为 false")
    passed = not details
    return _check(
        "safety-markers",
        passed,
        "G0 安全标记有效" if passed else "G0 安全标记不安全或缺失",
        details,
    )


def _check_references(fixture: dict[str, Any]) -> dict[str, Any]:
    known_ids, duplicate_ids = _collect_references(fixture)
    details = [f"发现重复实体 ID: {item}" for item in duplicate_ids]
    scenarios = _records(fixture.get("scenarios"))
    for scenario in scenarios:
        scenario_id = scenario.get("scenario_id", "<unknown>")
        refs = scenario.get("data_refs", [])
        if not isinstance(refs, list):
            details.append(f"{scenario_id}: data_refs 不是数组")
            continue
        for reference in refs:
            if reference not in known_ids:
                details.append(f"{scenario_id}: 未知引用 {reference}")

    for order in _records(fixture.get("orders")):
        customer_id = order.get("customer_id")
        if customer_id not in known_ids:
            details.append(f"{order.get('order_id', '<unknown>')}: customer_id 不存在 {customer_id}")
    for ticket in _records(fixture.get("tickets")):
        customer_id = ticket.get("customer_id")
        if customer_id not in known_ids:
            details.append(f"{ticket.get('ticket_id', '<unknown>')}: customer_id 不存在 {customer_id}")
    for session in _records(fixture.get("sessions")):
        user_id = session.get("user_id")
        if user_id not in known_ids:
            details.append(f"{session.get('session_id', '<unknown>')}: user_id 不存在 {user_id}")
    for approval in _records(fixture.get("approvals")):
        for field in ("session_id", "requester_id"):
            reference = approval.get(field)
            if reference not in known_ids:
                details.append(f"{approval.get('approval_id', '<unknown>')}: {field} 不存在 {reference}")
        approver_id = approval.get("approver_id")
        if approver_id is not None and approver_id not in known_ids:
            details.append(f"{approval.get('approval_id', '<unknown>')}: approver_id 不存在 {approver_id}")
    passed = not details
    return _check(
        "entity-references",
        passed,
        "实体引用完整" if passed else "实体引用校验失败",
        details,
    )


def _check_coverage(fixture: dict[str, Any]) -> dict[str, Any]:
    users = _records(fixture.get("users"))
    documents = _records(fixture.get("documents"))
    approvals = _records(fixture.get("approvals"))
    scenarios = _records(fixture.get("scenarios"))
    details: list[str] = []

    actual_roles = {user.get("role") for user in users}
    missing_roles = sorted(EXPECTED_ROLES - actual_roles)
    if missing_roles:
        details.append(f"缺少角色: {', '.join(missing_roles)}")

    actual_namespaces = {document.get("dept_namespace") for document in documents}
    missing_namespaces = sorted(EXPECTED_NAMESPACES - actual_namespaces)
    if missing_namespaces:
        details.append(f"缺少命名空间: {', '.join(missing_namespaces)}")

    scenario_ids = [scenario.get("scenario_id") for scenario in scenarios]
    if len(scenario_ids) != len(set(scenario_ids)):
        details.append("UAT 场景 ID 存在重复")
    if set(scenario_ids) != set(EXPECTED_SCENARIO_IDS):
        missing = sorted(set(EXPECTED_SCENARIO_IDS) - set(scenario_ids))
        extra = sorted(set(scenario_ids) - set(EXPECTED_SCENARIO_IDS))
        if missing:
            details.append(f"缺少 UAT 场景: {', '.join(missing)}")
        if extra:
            details.append(f"存在未计划 UAT 场景: {', '.join(extra)}")

    actual_approval_statuses = {approval.get("status") for approval in approvals}
    missing_statuses = sorted(REQUIRED_APPROVAL_STATUSES - actual_approval_statuses)
    if missing_statuses:
        details.append(f"缺少审批状态覆盖: {', '.join(missing_statuses)}")

    counts = fixture.get("counts")
    if isinstance(counts, dict):
        count_fields = {
            "users": users,
            "documents": documents,
            "approvals": approvals,
            "scenarios": scenarios,
        }
        for field, records in count_fields.items():
            if counts.get(field) != len(records):
                details.append(f"counts.{field} 与实际记录数不一致")
    passed = not details
    return _check(
        "coverage",
        passed,
        "角色、命名空间、场景和审批状态覆盖完整" if passed else "覆盖完整性校验失败",
        details,
    )


def _email_values(value: Any, key: str = "") -> Iterable[str]:
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            yield from _email_values(child_value, child_key.lower())
    elif isinstance(value, list):
        for child_value in value:
            yield from _email_values(child_value, key)
    elif isinstance(value, str) and key in {"email", "internal_email", "to", "cc", "reply_to"}:
        if "@" in value:
            yield value


def _find_unsafe_token_fields(value: Any, path: str = "") -> list[str]:
    unsafe: list[str] = []
    if isinstance(value, dict):
        for key, child_value in value.items():
            child_path = f"{path}.{key}" if path else key
            normalized = key.lower()
            if (
                (normalized.endswith("_token") or normalized in {"password", "password_hash", "secret"})
                and child_value not in (None, "", False)
            ):
                unsafe.append(child_path)
            unsafe.extend(_find_unsafe_token_fields(child_value, child_path))
    elif isinstance(value, list):
        for index, child_value in enumerate(value):
            unsafe.extend(_find_unsafe_token_fields(child_value, f"{path}[{index}]"))
    return unsafe


def _check_global_safety(fixture: dict[str, Any]) -> dict[str, Any]:
    details: list[str] = []
    safety = fixture.get("safety")
    if not isinstance(safety, dict) or safety.get("no_passwords_or_tokens") is not True:
        details.append("safety.no_passwords_or_tokens 必须为 true")
    unsafe_tokens = _find_unsafe_token_fields(fixture)
    if unsafe_tokens:
        details.append(f"发现非空敏感字段: {', '.join(unsafe_tokens)}")
    unsafe_emails = []
    for email in _email_values(fixture):
        domain = email.rsplit("@", 1)[-1].lower()
        if domain not in SAFE_EMAIL_DOMAINS:
            unsafe_emails.append(email)
    if unsafe_emails:
        details.append(f"发现非测试邮箱域名: {', '.join(unsafe_emails)}")
    if fixture.get("external_side_effects_allowed") is not False:
        details.append("外部副作用开关不是 false")
    if fixture.get("official_uat") is not False:
        details.append("fixture 被标记为正式 UAT")
    if fixture.get("import_mode") != "manual_review_only":
        details.append("import_mode 必须为 manual_review_only")
    passed = not details
    return _check(
        "global-safety",
        passed,
        "测试地址、token 和外部副作用边界有效" if passed else "全局安全边界校验失败",
        details,
    )


def _check_scenario(
    scenario: dict[str, Any],
    users: dict[str, dict[str, Any]],
    documents: dict[str, dict[str, Any]],
    sessions: dict[str, dict[str, Any]],
    approvals: dict[str, dict[str, Any]],
    fixture: dict[str, Any],
) -> dict[str, Any]:
    scenario_id = scenario.get("scenario_id", "<unknown>")
    details: list[str] = []
    actor_id = scenario.get("actor_user_id")
    actor = users.get(actor_id)
    if actor is None:
        details.append(f"actor_user_id 不存在: {actor_id}")

    data_refs = scenario.get("data_refs", [])
    if not isinstance(data_refs, list):
        details.append("data_refs 不是数组")
        data_refs = []

    known_ids = set(users) | set(documents) | set(sessions) | set(approvals)
    known_ids.update(
        record_id
        for collection, id_key in (
            ("customers", "customer_id"),
            ("orders", "order_id"),
            ("tickets", "ticket_id"),
        )
        for record_id in _index_records(_records(fixture.get(collection)), id_key)[0]
    )
    for reference in data_refs:
        if reference not in known_ids:
            details.append(f"未知场景引用: {reference}")

    contract = scenario.get("replay_contract")
    if not isinstance(contract, dict):
        details.append("缺少 replay_contract")
        contract = {}
    if contract.get("require_no_external_side_effects") is not True:
        details.append("场景未声明禁止外部副作用")
    if fixture.get("external_side_effects_allowed") is not False:
        details.append("fixture 允许外部副作用")

    if actor is not None:
        actor_role = actor.get("role")
        for access_check in contract.get("namespace_access", []):
            document_id = access_check.get("document_id")
            document = documents.get(document_id)
            if document is None:
                details.append(f"命名空间检查引用未知文档: {document_id}")
                continue
            actual = actor_role in document.get("access_roles", [])
            expected = access_check.get("expected") == "allow"
            if actual != expected:
                details.append(
                    f"{document_id} 命名空间结果不符: expected={access_check.get('expected')}, "
                    f"actual={'allow' if actual else 'deny'}"
                )

        for approval_check in contract.get("approval_checks", []):
            approval_id = approval_check.get("approval_id")
            approval = approvals.get(approval_id)
            if approval is None:
                details.append(f"审批检查引用未知审批: {approval_id}")
                continue
            expected_status = approval_check.get("expected_status")
            if approval.get("status") != expected_status:
                details.append(
                    f"{approval_id} 审批状态不符: expected={expected_status}, "
                    f"actual={approval.get('status')}"
                )
            if "actor_can_approve" in approval_check:
                expected_permission = approval_check["actor_can_approve"]
                if actor.get("can_approve") is not expected_permission:
                    details.append(
                        f"{approval_id} 审批权限不符: expected={expected_permission}, "
                        f"actual={actor.get('can_approve')}"
                    )

    required_session_status = contract.get("required_session_status")
    if required_session_status is not None:
        referenced_sessions = [sessions[item] for item in data_refs if item in sessions]
        if not referenced_sessions:
            details.append("场景声明会话状态但未引用会话")
        elif any(session.get("status") != required_session_status for session in referenced_sessions):
            details.append(f"会话状态不符: expected={required_session_status}")

    passed = not details
    return _check(
        f"scenario-{scenario_id}",
        passed,
        "场景回放契约通过" if passed else "场景回放契约失败",
        details,
        scenario_id=scenario_id,
    )


def run_replay(
    fixture: dict[str, Any],
    *,
    executed_at: str | None = None,
) -> dict[str, Any]:
    """执行一次回放并返回报告字典；不抛出业务校验异常。"""

    if not isinstance(fixture, dict):
        fixture = {}
    checks = [
        _check_safety_markers(fixture),
        _check_references(fixture),
        _check_coverage(fixture),
        _check_global_safety(fixture),
    ]
    users, _ = _index_records(_records(fixture.get("users")), "user_id")
    documents, _ = _index_records(_records(fixture.get("documents")), "document_id")
    sessions, _ = _index_records(_records(fixture.get("sessions")), "session_id")
    approvals, _ = _index_records(_records(fixture.get("approvals")), "approval_id")
    for scenario in _records(fixture.get("scenarios")):
        checks.append(_check_scenario(scenario, users, documents, sessions, approvals, fixture))

    failed_checks = [check for check in checks if check["status"] == "failed"]
    return {
        "report_version": "1.0.0",
        "fixture_id": fixture.get("fixture_id", "unknown"),
        "fixture_version": fixture.get("fixture_version"),
        "execution_mode": "G0 technical rehearsal",
        "executed_at": executed_at or datetime.now(UTC).isoformat(),
        "official_uat": False,
        "formal_uat": False,
        "release_evidence": False,
        "overall_status": "failed" if failed_checks else "passed",
        "failure_count": len(failed_checks),
        "checks": checks,
        "statement": "本报告仅为 G0 技术彩排，不是正式 UAT、真实外部系统联调或上线放行证据。",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# UAT G0 技术彩排回放报告",
        "",
        "> 本报告仅为 G0 技术彩排，不是正式 UAT、真实外部系统联调或上线放行证据。",
        "",
        f"- Fixture：`{report.get('fixture_id', 'unknown')}`",
        f"- 执行模式：`{report.get('execution_mode', 'G0 technical rehearsal')}`",
        f"- 执行时间：`{report.get('executed_at', '')}`",
        f"- 总结：`{report.get('overall_status', 'failed')}`",
        f"- 正式 UAT：`{str(report.get('formal_uat', False)).lower()}`",
        f"- 发布证据：`{str(report.get('release_evidence', False)).lower()}`",
        "",
        "## 检查结果",
        "",
        "| 检查项 | 状态 | 说明 |",
        "|---|---|---|",
    ]
    for check in report.get("checks", []):
        status = check.get("status", "failed")
        details = "；".join(check.get("details", []))
        lines.append(f"| `{check.get('check_id')}` | `{status}` | {check.get('message', '')} {details} |")
    lines.extend(["", "## 安全边界", "", report.get("statement", ""), ""])
    return "\n".join(lines)


def _load_fixture(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("fixture 根节点必须是 JSON 对象")
    return value


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="执行 UAT G0 技术彩排回放")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE, help="合成 fixture 路径")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_REPORT, help="JSON 报告路径")
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=DEFAULT_MARKDOWN_REPORT,
        help="Markdown 报告路径",
    )
    parser.add_argument("--executed-at", default=None, help="可选：注入固定执行时间，便于测试")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        fixture = _load_fixture(args.fixture)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"无法读取 fixture: {exc}", file=sys.stderr)
        return 2

    report = run_replay(fixture, executed_at=args.executed_at)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(f"JSON 报告: {args.json_output}")
    print(f"Markdown 报告: {args.markdown_output}")
    print(f"回放结果: {report['overall_status']}，失败检查数: {report['failure_count']}")
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
