"""Reviewed offline C21 source/memory entry; no application, disk database or receiver launch."""
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    sys.dont_write_bytecode = True
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_runtime_observability.py'),
                  run_name='__main__')
