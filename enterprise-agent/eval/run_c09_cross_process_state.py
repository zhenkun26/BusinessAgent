"""Reviewed C09 offline entry; shared doubles only, no real services or cleanup."""

from pathlib import Path
import runpy
import sys


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_cross_process_state.py'),
                  run_name='__main__')
