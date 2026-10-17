"""Fail closed on plans outside the independent fan-out contract."""

from __future__ import annotations

from typing import Any


class PlanRejected(ValueError):
    """A fixed public reason, never model output."""


def check_dependencies(value: Any) -> None:
    """Only an omitted field or an empty list represents an independent task."""
    if not isinstance(value, list):
        raise PlanRejected("INVALID_TASK_DEPENDENCIES")
    if value:
        raise PlanRejected("TASK_DEPENDENCIES_UNSUPPORTED")


def check_plan(subtasks: list[Any]) -> None:
    """Inspect every task before constructing any Send objects."""
    for task in subtasks:
        check_dependencies(task.get("depends_on", []) if isinstance(task, dict)
                           else task.depends_on)
