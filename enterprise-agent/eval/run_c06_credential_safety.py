"""Run C06 reviewed offline Python tests; browser-script checks have a separate Node entry."""

from pathlib import Path
import runpy
import sys


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_credential_safety.py'),
                  run_name='__main__')
