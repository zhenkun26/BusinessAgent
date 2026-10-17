"""Reviewed C10 offline entry: injected savers only, no stores or file cleanup."""

from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    sys.dont_write_bytecode = True
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_checkpoint_durability.py'),
                  run_name='__main__')
