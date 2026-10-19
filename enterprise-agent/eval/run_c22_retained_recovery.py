"""Reviewed C22 offline entry: retained synthetic files and injected Docker only."""
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    sys.dont_write_bytecode = True
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_retained_recovery.py'),
                  run_name='__main__')
