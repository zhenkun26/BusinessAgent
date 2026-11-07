"""Reviewed C08 offline entry: no live services, filesystem writes or cleanup."""

from pathlib import Path
import runpy
import sys


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    # Resolve the shared stdlib-only admission policy used by source-loaded fixtures.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_request_context.py'),
                  run_name='__main__')
