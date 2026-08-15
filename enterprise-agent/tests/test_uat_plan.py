"""UAT 计划与 G0 fixture 的结构校验测试。"""

from __future__ import annotations

from pathlib import Path

from eval.validate_uat_plan import validate_uat_plan

PROJECT_ROOT = Path(__file__).parents[2]
PLAN_PATH = PROJECT_ROOT / "docs/30-guides/UAT验收计划.md"
FIXTURE_PATH = Path(__file__).parents[1] / "eval/uat_simulation/fixture.json"


def test_should_accept_plan_when_matrix_and_fixture_cover_same_scenarios():
    report = validate_uat_plan(PLAN_PATH, FIXTURE_PATH)

    assert report["overall_status"] == "passed"
    assert report["formal_uat"] is False
    assert report["release_evidence"] is False
    assert report["execution_ready"] is False
    assert all(check["passed"] for check in report["checks"])


def test_should_reject_plan_when_matrix_contains_duplicate_scenario(tmp_path):
    content = PLAN_PATH.read_text(encoding="utf-8")
    duplicate = (
        "| UAT-K01 | 重复场景 | 销售 | §4 | 重复检查 | 不应通过 |\n\n"
    )
    mutated = content.replace("## 5. 场景通过标准", duplicate + "## 5. 场景通过标准")
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(mutated, encoding="utf-8")

    report = validate_uat_plan(plan_path, FIXTURE_PATH)

    assert report["overall_status"] == "failed"
    failed = {check["name"] for check in report["checks"] if not check["passed"]}
    assert "matrix_covers_each_scenario_once" in failed
