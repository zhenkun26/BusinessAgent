"""发布门槛检查单核对测试。"""

from __future__ import annotations

from pathlib import Path

from eval.validate_release_gate import validate_release_gate

PROJECT_ROOT = Path(__file__).parents[2]
CHECKLIST_PATH = PROJECT_ROOT / "docs/30-guides/发布灰度与上线门槛检查单.md"


def test_should_keep_release_blocked_when_gate_evidence_is_incomplete():
    report = validate_release_gate(CHECKLIST_PATH, PROJECT_ROOT)

    assert report["overall_status"] == "blocked"
    assert report["release_allowed"] is False
    assert report["formal_release"] is False
    assert report["ready_gate_ids"] == ["GATE-02", "GATE-05"]
    assert report["blocked_gate_ids"] == ["GATE-01", "GATE-03", "GATE-04", "GATE-06"]
    assert all(check["passed"] for check in report["checks"])


def test_should_reject_checklist_with_duplicate_gate_id(tmp_path):
    content = CHECKLIST_PATH.read_text(encoding="utf-8")
    mutated = content.replace("| GATE-06 |", "| GATE-05 |", 1)
    checklist_path = tmp_path / "checklist.md"
    checklist_path.write_text(mutated, encoding="utf-8")

    report = validate_release_gate(checklist_path, PROJECT_ROOT)

    assert report["overall_status"] == "invalid"
    failed = {check["name"] for check in report["checks"] if not check["passed"]}
    assert "gate_ids_complete" in failed
