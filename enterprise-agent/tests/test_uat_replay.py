"""G0 UAT 回放器的安全与完整性测试。"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from eval.run_uat_replay import render_markdown, run_replay

FIXTURE_PATH = Path(__file__).parents[1] / "eval" / "uat_simulation" / "fixture.json"


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _check(report: dict[str, Any], check_id: str) -> dict[str, Any]:
    return next(item for item in report["checks"] if item["check_id"] == check_id)


def test_valid_fixture_passes_all_replay_checks() -> None:
    report = run_replay(_load_fixture(), executed_at="2026-08-15T12:00:00+00:00")

    assert report["overall_status"] == "passed"
    assert report["failure_count"] == 0
    assert report["formal_uat"] is False
    assert report["release_evidence"] is False
    assert _check(report, "scenario-UAT-K02")["status"] == "passed"


def test_namespace_negative_case_is_checked_as_expected_denial() -> None:
    report = run_replay(_load_fixture())
    scenario_check = _check(report, "scenario-UAT-K02")

    assert scenario_check["status"] == "passed"
    assert _check(report, "coverage")["status"] == "passed"


def test_unsafe_fixture_marker_fails_without_formal_uat_label() -> None:
    fixture = copy.deepcopy(_load_fixture())
    fixture["external_side_effects_allowed"] = True

    report = run_replay(fixture)

    assert report["overall_status"] == "failed"
    assert report["formal_uat"] is False
    assert _check(report, "safety-markers")["status"] == "failed"
    assert "外部副作用" in render_markdown(report)


def test_unknown_scenario_reference_is_reported_independently() -> None:
    fixture = copy.deepcopy(_load_fixture())
    fixture["scenarios"][0]["data_refs"].append("SIM-NOT-FOUND")

    report = run_replay(fixture)

    assert report["overall_status"] == "failed"
    assert _check(report, "entity-references")["status"] == "failed"
    assert _check(report, "scenario-UAT-K01")["status"] == "failed"
    assert _check(report, "scenario-UAT-K02")["status"] == "passed"


def test_real_email_domain_is_rejected() -> None:
    fixture = copy.deepcopy(_load_fixture())
    fixture["approvals"][0]["prefill_payload"]["to"] = ["real@example.com"]

    report = run_replay(fixture)

    assert report["overall_status"] == "failed"
    assert _check(report, "global-safety")["status"] == "failed"
