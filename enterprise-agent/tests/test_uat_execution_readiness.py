"""UAT 执行准备度核验测试。"""

from __future__ import annotations

from pathlib import Path

from eval.validate_uat_execution_readiness import validate_uat_execution_readiness

PROJECT_ROOT = Path(__file__).parents[2]
PLAN_PATH = PROJECT_ROOT / "docs/30-guides/UAT验收计划.md"


def test_should_block_formal_uat_when_resources_are_pending():
    report = validate_uat_execution_readiness(PLAN_PATH)

    assert report["overall_status"] == "blocked"
    assert report["execution_ready"] is False
    assert report["formal_uat"] is False
    assert report["unresolved_resources"] == [
        "真实验收用户",
        "验收环境",
        "验收窗口",
        "外部系统范围",
        "结果签署人",
    ]
    assert all(check["passed"] for check in report["checks"][2:])


def test_should_reject_execution_template_with_non_pending_result(tmp_path):
    content = PLAN_PATH.read_text(encoding="utf-8").replace(
        "| UAT-K01 | 待填 | 待填 | 待填 | 待执行 |",
        "| UAT-K01 | 模拟用户 | G0 | 2026-08-15 | 通过 |",
    )
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(content, encoding="utf-8")

    report = validate_uat_execution_readiness(plan_path)

    assert report["overall_status"] == "invalid"
    failed = {check["name"] for check in report["checks"] if not check["passed"]}
    assert "execution_template_is_untouched" in failed
