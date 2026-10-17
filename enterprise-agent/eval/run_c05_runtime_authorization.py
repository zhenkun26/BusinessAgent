"""Run reviewed offline C05 checks without application startup or external access."""

from pathlib import Path
import runpy
import sys


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "tests/test_runtime_authorization.py"),
        run_name="__main__",
    )
