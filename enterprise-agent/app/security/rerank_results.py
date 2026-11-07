"""Local result contracts for optional non-generative rerank backends."""
from __future__ import annotations

import math
from numbers import Real
from typing import Any

import numpy as np

from app.core.execution_budget import check_execution_budget


class OptionalRerankError(RuntimeError):
    def __init__(self) -> None:
        super().__init__('OPTIONAL_RERANK_RESULT_REJECTED')


def _text(value: Any) -> str:
    if type(value) is not str or not value.strip():
        raise OptionalRerankError()
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise OptionalRerankError() from None
    return value


def candidate_texts(query: str, candidates: list[Any], top_n: int) -> list[str]:
    check_execution_budget()
    if type(top_n) is not int or top_n < 1 or type(candidates) is not list:
        raise OptionalRerankError()
    if not candidates:
        return []
    _text(query)
    return [_text(candidate.content) for candidate in candidates]


def _finite_real(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise OptionalRerankError()
    result = float(value)
    if not math.isfinite(result):
        raise OptionalRerankError()
    return result


def cohere_scores(rows: Any, candidate_count: int, top_n: int) -> list[tuple[int, float]]:
    check_execution_budget()
    if type(rows) is not list or len(rows) != min(top_n, candidate_count):
        raise OptionalRerankError()
    seen = set()
    result = []
    for row in rows:
        if type(row) is dict:
            index, value = row.get('index'), row.get('relevance_score')
        else:
            index = getattr(row, 'index', None)
            value = getattr(row, 'relevance_score', None)
        if type(index) is not int or not 0 <= index < candidate_count or index in seen:
            raise OptionalRerankError()
        score = _finite_real(value)
        if not 0 <= score <= 1:
            raise OptionalRerankError()
        seen.add(index)
        result.append((index, score))
    return sorted(result, key=lambda item: (-item[1], item[0]))


def bge_scores(values: Any, candidate_count: int, top_n: int) -> list[tuple[int, float]]:
    check_execution_budget()
    if isinstance(values, np.ndarray):
        if values.ndim != 1:
            raise OptionalRerankError()
    elif type(values) not in (list, tuple):
        raise OptionalRerankError()
    if len(values) != candidate_count:
        raise OptionalRerankError()
    result = []
    for index, value in enumerate(values):
        logit = _finite_real(value)
        # Preserve the existing sigmoid contract without positive exponent overflow.
        if logit >= 0:
            score = 1.0 / (1.0 + math.exp(-logit))
        else:
            numerator = math.exp(logit)
            score = numerator / (1.0 + numerator)
        result.append((index, score))
    return sorted(result, key=lambda item: (-item[1], item[0]))[:top_n]
