"""C23 plan/report/runtime CLI; no network without --execute and a matching plan digest."""
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capacity.runner import main

if __name__ == '__main__':
    raise SystemExit(main())
