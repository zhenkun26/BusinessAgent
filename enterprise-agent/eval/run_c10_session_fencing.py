"""Reviewed C10 fencing entry; deterministic clocks/stores, no service access or cleanup."""
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    sys.dont_write_bytecode = True
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_session_fencing.py'),
                  run_name='__main__')
