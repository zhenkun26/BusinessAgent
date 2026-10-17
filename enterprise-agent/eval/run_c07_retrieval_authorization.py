"""Reviewed C07 offline entry; no real stores, models or filesystem cleanup."""

from pathlib import Path
import runpy
import sys


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_retrieval_authorization.py'),
                  run_name='__main__')
