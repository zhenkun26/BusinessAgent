"""灰度方案结构核验测试。"""

from __future__ import annotations

from pathlib import Path

from eval.validate_grey_release_plan import validate_grey_release_plan

PROJECT_ROOT = Path(__file__).parents[2]
PLAN_PATH = PROJECT_ROOT / "docs/30-guides/发布灰度与上线门槛检查单.md"


def test_should_block_plan_when_g3_observation_has_no_upper_bound(tmp_path):
    content = PLAN_PATH.read_text(encoding="utf-8").replace(
        "G3 | 全部目标用户 | 2 周 |", "G3 | 全部目标用户 | 2 周以上 |"
    )
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(content, encoding="utf-8")

    report = validate_grey_release_plan(plan_path)

    assert report["overall_status"] == "needs_revision"
    assert report["review_conclusion"] == "blocked"
    assert report["plan_approval"] is False
    failed = {check["name"] for check in report["checks"] if not check["passed"]}
    assert failed == {"observation_window_is_bounded"}


def test_should_accept_bounded_observation_window_for_structural_review(tmp_path):
    report = validate_grey_release_plan(PLAN_PATH)

    assert report["overall_status"] == "passed"
    assert report["review_conclusion"] == "conditional"
    assert report["execution_ready"] is False
    assert report["owner_confirmation_pending"] is True
