"""Run the approved offline checks without filesystem deletion or network access.

From the repository root, using the existing Python 3.13/site-packages:
PYTHONPATH=enterprise-agent/.venv/lib/python3.13/site-packages python -B \
    docs/40-process/code-simplification/20260928-backend/verify.py baseline
Replace baseline with final after applying the approved production edits.
Outputs use exclusive creation and are retained; choose a new phase for a retry.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone


EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[3]
BACKEND = ROOT / "enterprise-agent"
PHASE = sys.argv[1]
if PHASE not in {"baseline", "final"} and not PHASE.startswith(("baseline-", "final-")):
    raise ValueError("Use baseline/final or a uniquely suffixed retry phase")
OUTPUT = EVIDENCE / f"{PHASE}.json"
if OUTPUT.exists():
    raise FileExistsError("Evidence already exists; use a new retry phase")

sys.dont_write_bytecode = True
sys.path.insert(0, str(BACKEND))
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
os.environ.pop("PYTEST_ADDOPTS", None)
os.environ.pop("PYTEST_PLUGINS", None)
os.chdir(BACKEND)
blocked: list[str] = []


def guard(event: str, args: tuple) -> None:
    forbidden = event in {"os.remove", "os.rmdir", "shutil.rmtree", "socket.connect", "socket.bind"}
    if event == "open" and isinstance(args[0], (str, bytes)):
        flags = args[2]
        write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC
        writes = isinstance(flags, int) and flags & write_flags
        forbidden = bool(writes and Path(os.fsdecode(args[0])).resolve() != OUTPUT)
    if forbidden:
        blocked.append(event)
        raise RuntimeError(f"Forbidden verification side effect: {event}")


sys.addaudithook(guard)

import coverage
import pytest

targets = [BACKEND / "app/rag/vector_store.py", BACKEND / "app/middleware/rate_limit.py"]
cov = coverage.Coverage(data_file=None, config_file=False, include=[str(p) for p in targets])
cov.start()

from app.rag.vector_store import ChunkData, InMemoryVectorStore, SearchFilter

store = InMemoryVectorStore(dim=2)
assert store.search([1.0, 0.0]) == []
assert store.add_documents([]) == 0
chunks = [
    ChunkData("shared", "d1", "Shared", "Shared", [1.0, 0.0], updated_at=0,
              access_roles=["salesperson"]),
    ChunkData("sales", "d2", "Sales", "Sales", [0.8, 0.6], dept_namespace="sales",
              updated_at=0, access_roles=["salesperson"]),
    ChunkData("finance", "d3", "Finance", "Finance", [1.0, 0.0], dept_namespace="finance",
              updated_at=0, access_roles=["finance"]),
    ChunkData("inactive", "d4", "Old", "Old", [1.0, 0.0], updated_at=0,
              access_roles=["salesperson"], is_active=False),
]
assert store.add_documents(chunks) == 4
selected = store.search(
    [1.0, 0.0], filter=SearchFilter(user_role="salesperson", dept_namespace="sales"),
)
assert [row.chunk_id for row in selected] == ["shared", "sales"]
assert selected[0].score == 1.0 and abs(selected[1].score - 0.8) < 1e-6
assert store.search([1.0, 0.0], filter=SearchFilter(doc_types=["missing"])) == []
try:
    store.add_documents([ChunkData("bad", "bad", "Bad", "Bad", [1.0], updated_at=0)])
except ValueError:
    pass
else:
    raise AssertionError("Dimension mismatch was accepted")
assert store.get_stats()["total_entities"] == 4
assert store.delete_document("d2") == 1
assert store.delete_document("missing") == 0
assert store.get_stats()["total_entities"] == 3
for document_id in ("d1", "d3", "d4"):
    assert store.delete_document(document_id) == 1
assert store.search([1.0, 0.0]) == []
assert store.get_stats() == {
    "provider": "memory", "total_entities": 0, "dim": 2, "partitions": [],
}
memory_checks = {"empty": True, "add": True, "ranking": True, "role_namespace_filter": True,
                 "type_filter": True, "dimension_rejection": True, "memory_removal": True, "stats": True}


class Results:
    def __init__(self) -> None:
        self.collected = 0
        self.outcomes = {"passed": 0, "failed": 0, "skipped": 0, "xfailed": 0}

    def pytest_collection_finish(self, session) -> None:
        self.collected = len(session.items)

    def pytest_runtest_logreport(self, report) -> None:
        if report.failed:
            self.outcomes["failed"] += 1
        elif report.skipped:
            self.outcomes["xfailed" if hasattr(report, "wasxfail") else "skipped"] += 1
        elif report.when == "call" and report.passed:
            self.outcomes["passed"] += 1


results = Results()
pytest_args = ["tests/test_rate_limit.py", "tests/test_http_adapter.py", "-q",
               "-p", "no:cacheprovider", "-p", "no:tmpdir", "-p", "no:capture", "-p", "no:logging",
               "-p", "pytest_asyncio.plugin"]
exit_code = int(pytest.main(pytest_args, plugins=[results]))
cov.stop()
line_coverage = {}
for target in targets:
    _, statements, excluded, missing, _ = cov.analysis2(str(target))
    line_coverage[str(target.relative_to(ROOT))] = {
        "covered": len(statements) - len(missing), "total": len(statements),
        "excluded": excluded, "missing": missing,
    }
syntax_paths = targets + [BACKEND / "tests/test_rate_limit.py", Path(__file__)]
for target in syntax_paths:
    ast.parse(target.read_text(encoding="utf-8"), filename=str(target))
payload = {
    "phase": PHASE, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "cwd": str(BACKEND.relative_to(ROOT)), "python": sys.version.split()[0],
    "packages": {name: importlib.metadata.version(name) for name in
                 ("pytest", "pytest-asyncio", "coverage", "numpy", "fastapi")},
    "pytest_args": pytest_args, "pytest_exit_code": exit_code,
    "tests_collected": results.collected, "test_outcomes": results.outcomes,
    "memory_checks": memory_checks, "coverage": line_coverage, "syntax": "passed",
    "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in syntax_paths},
    "blocked_side_effects": blocked,
    "limitations": ["Focused checks only; no full suite, external services, CI or Python 3.11 run",
                    "Memory coverage, without pytest-cov erase/save or filesystem artifacts"],
}
with OUTPUT.open("x", encoding="utf-8") as stream:
    json.dump(payload, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps(payload, ensure_ascii=False, indent=2))
raise SystemExit(exit_code or (1 if blocked else 0))
