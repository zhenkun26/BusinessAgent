"""Reviewed C23 offline tests: injected HTTP/clock, in-memory reference ledger only."""
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    sys.dont_write_bytecode = True
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_capacity_evidence.py'),
                  run_name='__main__')
