"""C10 source/history offline entry; declared dependencies, no services or cleanup."""
from pathlib import Path
import runpy
import socket
import sys

denials: list[str] = []


def deny(code: str) -> None:
    denials.append(code)
    raise RuntimeError(code)


def guard(event: str, args: tuple) -> None:
    if event == 'socket.__new__' and args[1] == socket.AF_UNIX:
        return  # asyncio self-pipe only; network operations remain forbidden.
    if event.startswith(('socket.', 'subprocess.')) or event in {
        'os.remove', 'os.rmdir', 'os.rename', 'os.system', 'os.mkdir', 'os.chmod',
        'os.chown', 'os.truncate', 'os.utime', 'os.link', 'os.symlink',
    }:
        deny('OFFLINE_SIDE_EFFECT_DENIED')
    if event == 'open' and isinstance(args[0], (str, bytes)):
        name = args[0].decode() if isinstance(args[0], bytes) else args[0]
        if Path(name).name in {'.env', '.env.local'}:
            deny('OFFLINE_ENV_FILE_DENIED')
    if event == 'open' and (isinstance(args[1], str) and any(c in args[1] for c in 'wax+')
                            or isinstance(args[2], int) and args[2] & 3):
        deny('OFFLINE_WRITE_DENIED')


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.addaudithook(guard)
    # urllib3's optional IPv6 import probe is unavailable in this offline process.
    ipv6 = socket.has_ipv6
    try:
        socket.has_ipv6 = False
        import urllib3
    finally:
        socket.has_ipv6 = ipv6
    try:
        runpy.run_path(str(Path(__file__).resolve().parents[1]
                          / 'tests/test_checkpoint_followups.py'), run_name='__main__')
    finally:
        if denials:
            raise RuntimeError('OFFLINE_GUARD_DENIALS')
        print('Offline guard: zero denials; runtime/full RAG BLOCKED; C10 OPEN.')
