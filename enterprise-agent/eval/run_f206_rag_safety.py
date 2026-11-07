"""Print synthetic checker evidence only; no models, writes, network or cleanup."""
from pathlib import Path
import json
import runpy
import sys
from typing import Any


def guard(event: str, args: tuple[Any, ...]) -> None:
    if event.startswith(("socket.", "subprocess.", "ctypes.")) or event in {
        "os.remove", "os.rmdir", "os.rename", "os.system", "os.mkdir", "os.chmod", "os.chown",
        "os.truncate", "os.utime", "os.link", "os.symlink", "os.exec", "os.posix_spawn",
        "os.fork", "os.forkpty", "os.putenv", "os.unsetenv",
    }:
        raise RuntimeError("OFFLINE_SIDE_EFFECT_DENIED")
    if event == "open" and (
        isinstance(args[1], str) and any(c in args[1] for c in "wax+")
        or isinstance(args[2], int) and args[2] & 3
    ):
        raise RuntimeError("OFFLINE_WRITE_DENIED")


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.addaudithook(guard)
    checker = runpy.run_path(str(Path(__file__).with_name("rag_safety.py")))
    report = checker["verify_controls"]()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # Zero means the authored checker controls passed, never runtime/model acceptance.
    raise SystemExit(0 if report["checker_verification"] == "PASS" else 1)
