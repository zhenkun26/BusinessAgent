"""Reviewed offline C19 entry; no dependencies installed or live crypto/IdP/browser."""
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    sys.dont_write_bytecode = True
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_controlled_sso.py'),
                  run_name='__main__')
