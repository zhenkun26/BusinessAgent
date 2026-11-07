"""Reviewed C13 offline entry: no services, filesystem writes or cleanup."""
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    sys.dont_write_bytecode = True
    # Resolve the shared stdlib-only admission policy used by source-loaded fixtures.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    # Fixtures replace app.core with a stub; preload only the real stdlib policy.
    from app.core import execution_budget  # noqa: F401

    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_saga_recovery.py'),
                  run_name='__main__')
