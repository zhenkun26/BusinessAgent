"""Numeric admission only; does not normalize, rank or calibrate relevance."""
from __future__ import annotations

import math
from numbers import Real
from typing import Any


class ScoreAdmissionError(ValueError):
    def __init__(self) -> None:
        super().__init__("RAG_SCORE_INVALID")


def finite_score(value: Any) -> float:
    """Validate before coercion/clipping; never stringify rejected provider data."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ScoreAdmissionError()
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        raise ScoreAdmissionError() from None
    if not math.isfinite(number):
        raise ScoreAdmissionError()
    return number


def check_result_scores(results: list[Any]) -> None:
    """Reject the complete visible batch, including invalid non-first rows."""
    for result in results:
        finite_score(getattr(result, "score", None))
