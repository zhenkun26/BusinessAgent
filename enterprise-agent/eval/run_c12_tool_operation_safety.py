"""Reviewed C12 offline entry; injected stores/HTTP only, no services or cleanup."""
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    sys.dont_write_bytecode = True
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_tool_operation_safety.py'),
                  run_name='__main__')
