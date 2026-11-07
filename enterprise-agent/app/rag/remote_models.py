"""Bounded Bailian HTTP adapters using the project's existing httpx dependency."""

from __future__ import annotations

import math
import time
from typing import Any
from urllib.parse import urlsplit

import httpx


class RemoteModelError(RuntimeError):
    """A fixed, safe code; never includes provider bodies, text or credentials."""


def validate_text(text: str, byte_limit: int) -> None:
    # Conservative UTF-8 byte limit, not an exact tokenizer or a billing estimate.
    # Reject rather than silently truncate knowledge or queries.
    if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > byte_limit:
        raise RemoteModelError("MODEL_INPUT_INVALID")


def check_vector(vector: Any, dimensions: int) -> None:
    if (not isinstance(vector, list) or len(vector) != dimensions
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in vector)
            or not any(v != 0 for v in vector)):
        raise RemoteModelError("MODEL_VECTOR_INVALID")


def is_beijing_url(value: str, path: str) -> bool:
    try:
        url = urlsplit(value)
        host = url.hostname or ""
        workspace = host.removesuffix(".cn-beijing.maas.aliyuncs.com")
        valid_host = host == "dashscope.aliyuncs.com" or (
            host.endswith(".cn-beijing.maas.aliyuncs.com")
            and bool(workspace) and all(c.isalnum() or c == "-" for c in workspace)
        )
        return bool(valid_host and url.scheme == "https" and url.port in (None, 443)
                    and not (url.username or url.password or url.query or url.fragment)
                    and url.path.rstrip("/") == path)
    except (ValueError, TypeError):
        return False


class BailianClient:
    """No client construction performs I/O. Each request closes its own transport."""

    def __init__(self, base_url: str, api_key: str, timeout: float, retries: int,
                 *, kind: str) -> None:
        path = ("/compatible-mode/v1" if kind == "embedding"
                else "/api/v1/services/rerank/text-rerank")
        if (kind not in {"embedding", "reranker"} or not is_beijing_url(base_url, path)
                or not api_key.strip() or not 0 < timeout <= 60
                or type(retries) is not int or not 0 <= retries <= 2):
            raise RemoteModelError("MODEL_REMOTE_CONFIG_INVALID")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._retries = retries

    def post(self, suffix: str, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self._retries + 1):
            try:
                with httpx.Client(timeout=self._timeout, follow_redirects=False) as client:
                    response = client.post(
                        self._base_url + suffix,
                        headers={"Authorization": "Bearer " + self._api_key}, json=payload,
                    )
                if response.status_code in (408, 429) or 500 <= response.status_code <= 599:
                    if attempt < self._retries:
                        time.sleep(0.5 * (2 ** attempt))
                        continue
                    raise RemoteModelError("MODEL_REMOTE_UNAVAILABLE")
                if not 200 <= response.status_code < 300:
                    raise RemoteModelError("MODEL_REMOTE_REJECTED")
                data = response.json()
                if not isinstance(data, dict) or "error" in data or "code" in data:
                    raise RemoteModelError("MODEL_REMOTE_RESPONSE_INVALID")
                return data
            except httpx.TransportError:
                if attempt < self._retries:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                raise RemoteModelError("MODEL_REMOTE_UNAVAILABLE") from None
            except RemoteModelError:
                raise
            except Exception:
                raise RemoteModelError("MODEL_REMOTE_RESPONSE_INVALID") from None
        raise RemoteModelError("MODEL_REMOTE_UNAVAILABLE")

    def embed(self, texts: list[str], model: str, dimensions: int) -> list[list[float]]:
        for text in texts:
            validate_text(text, 8192)
        vectors: list[list[float]] = []
        for start in range(0, len(texts), 10):
            batch = texts[start:start + 10]
            data = self.post("/embeddings", {
                "model": model, "input": batch, "dimensions": dimensions,
                "encoding_format": "float",
            })
            rows = data.get("data")
            if not isinstance(rows, list) or len(rows) != len(batch):
                raise RemoteModelError("MODEL_EMBEDDING_RESPONSE_INVALID")
            indexed: dict[int, list[float]] = {}
            for row in rows:
                if not isinstance(row, dict):
                    raise RemoteModelError("MODEL_EMBEDDING_RESPONSE_INVALID")
                index, vector = row.get("index"), row.get("embedding")
                if type(index) is not int or not 0 <= index < len(batch) or index in indexed:
                    raise RemoteModelError("MODEL_EMBEDDING_RESPONSE_INVALID")
                check_vector(vector, dimensions)
                indexed[index] = vector
            vectors.extend(indexed[i] for i in range(len(batch)))
        return vectors

    def rerank(self, query: str, documents: list[str], model: str,
               top_n: int) -> list[tuple[int, float]]:
        if type(top_n) is not int or top_n < 1 or len(documents) > 500:
            raise RemoteModelError("MODEL_INPUT_INVALID")
        if not documents:
            return []
        validate_text(query, 4000)
        for document in documents:
            validate_text(document, 4000)
        count = min(top_n, len(documents))
        data = self.post("/text-rerank", {
            "model": model, "input": {"query": query, "documents": documents},
            "parameters": {"top_n": count, "return_documents": False},
        })
        output = data.get("output")
        rows = output.get("results") if isinstance(output, dict) else None
        if not isinstance(rows, list) or len(rows) != count:
            raise RemoteModelError("MODEL_RERANK_RESPONSE_INVALID")
        seen: set[int] = set()
        result: list[tuple[int, float]] = []
        for row in rows:
            if not isinstance(row, dict):
                raise RemoteModelError("MODEL_RERANK_RESPONSE_INVALID")
            index, score = row.get("index"), row.get("relevance_score")
            if (type(index) is not int or not 0 <= index < len(documents) or index in seen
                    or type(score) not in (int, float) or not math.isfinite(score)
                    or not 0 <= score <= 1):
                raise RemoteModelError("MODEL_RERANK_RESPONSE_INVALID")
            seen.add(index)
            result.append((index, float(score)))
        return sorted(result, key=lambda item: item[1], reverse=True)
