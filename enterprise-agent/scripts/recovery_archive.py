"""Retained cold-volume archives. Never removes, replaces or follows filesystem links."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tarfile
from typing import Any, BinaryIO

MAX_MEMBERS = 2_000_000
MAX_BYTES = 4 * 1024**4


def digest(stream: BinaryIO) -> str:
    value = hashlib.sha256()
    while block := stream.read(1024 * 1024):
        value.update(block)
    return value.hexdigest()


def file_hash(path: Path) -> str:
    with path.open('rb') as stream:
        return digest(stream)


def safe_path(path: Path) -> Path:
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('RECOVERY_PATH_REJECTED')
    return path


def member_name(name: str) -> str:
    if (not isinstance(name, str) or '\\' in name or '\x00' in name
            or name.startswith('/') or '..' in name.split('/')
            or name != PurePosixPath(name).as_posix() or not name):
        raise ValueError('ARCHIVE_PATH_REJECTED')
    return name


def metadata(path: Path, name: str) -> dict[str, Any]:
    info = path.lstat()
    is_dir = stat.S_ISDIR(info.st_mode)
    if (not is_dir and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1)
            or info.st_mode & 0o7000):
        raise ValueError('ARCHIVE_TYPE_REJECTED')
    return {'name': member_name(name), 'directory': is_dir, 'uid': info.st_uid,
            'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode),
            'size': 0 if is_dir else info.st_size,
            'sha256': None if is_dir else file_hash(path)}


def scan(root: Path) -> list[dict[str, Any]]:
    safe_path(root)
    rows = [metadata(root, '.')]
    total = 0
    for folder, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(folder) / name
            row = metadata(path, path.relative_to(root).as_posix())
            total += row['size']
            rows.append(row)
            if len(rows) > MAX_MEMBERS or total > MAX_BYTES:
                raise ValueError('ARCHIVE_LIMIT_EXCEEDED')
    return sorted(rows, key=lambda row: row['name'])


def verify_stream(archive: tarfile.TarFile, rows: list[dict[str, Any]]) -> None:
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_MEMBERS:
        raise ValueError('ARCHIVE_MANIFEST_REJECTED')
    expected = {member_name(row['name']): row for row in rows}
    if len(expected) != len(rows) or not expected.get('.', {}).get('directory'):
        raise ValueError('ARCHIVE_MANIFEST_REJECTED')
    seen = set()
    total = 0
    for member in archive:
        name = member_name(member.name)
        if name in seen or name not in expected or not (member.isfile() or member.isdir()):
            raise ValueError('ARCHIVE_MEMBER_REJECTED')
        if member.mode & 0o7000 or member.uid < 0 or member.gid < 0:
            raise ValueError('ARCHIVE_METADATA_REJECTED')
        parent = str(PurePosixPath(name).parent)
        if name != '.' and not expected.get(parent, {}).get('directory'):
            raise ValueError('ARCHIVE_PARENT_REJECTED')
        row = {'name': name, 'directory': member.isdir(), 'uid': member.uid,
               'gid': member.gid, 'mode': member.mode, 'size': member.size,
               'sha256': None}
        total += member.size
        if member.size < 0 or total > MAX_BYTES or len(seen) >= MAX_MEMBERS:
            raise ValueError('ARCHIVE_LIMIT_EXCEEDED')
        if member.isfile():
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError('ARCHIVE_CONTENT_MISSING')
            with stream:
                row['sha256'] = digest(stream)
        if row != expected[name]:
            raise ValueError('ARCHIVE_CONTENT_MISMATCH')
        seen.add(name)
    if seen != set(expected):
        raise ValueError('ARCHIVE_MEMBERS_MISSING')


def verify(path: Path, rows: list[dict[str, Any]]) -> None:
    safe_path(path)
    with tarfile.open(path, 'r:') as archive:
        verify_stream(archive, rows)


def sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_json(path: Path, value: Any) -> None:
    safe_path(path)
    with path.open('x', encoding='utf-8') as stream:
        os.chmod(path, 0o600)
        json.dump(value, stream, sort_keys=True, separators=(',', ':'))
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


def pack(source: Path, bundle: Path, name: str) -> None:
    safe_path(source); safe_path(bundle)
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_.-' for c in name):
        raise ValueError('ARCHIVE_NAME_REJECTED')
    rows = scan(source)
    path = bundle / (name + '.tar')
    with tarfile.open(path, 'x:', dereference=False) as archive:
        os.chmod(path, 0o600)
        for row in rows:
            archive.add(source if row['name'] == '.' else source / row['name'],
                        arcname=row['name'], recursive=False)
    with path.open('rb') as stream:
        os.fsync(stream.fileno())
    verify(path, rows)
    write_json(bundle / (name + '.json'), {'sha256': file_hash(path), 'members': rows})


def restore(path: Path, rows: list[dict[str, Any]], target: Path) -> None:
    safe_path(target)
    verify(path, rows)  # Complete verification before any target writes.
    if not target.is_dir() or any(target.iterdir()):
        raise ValueError('RESTORE_TARGET_NOT_EMPTY')
    with tarfile.open(path, 'r:') as archive:
        members = {member.name: member for member in archive}
        for name in sorted(members, key=lambda value: (len(PurePosixPath(value).parts), value)):
            member = members[name]
            destination = target if name == '.' else target / name
            safe_path(destination)
            if name == '.':
                continue
            if member.isdir():
                destination.mkdir(mode=0o700)
            else:
                source = archive.extractfile(member)
                assert source is not None
                with source, destination.open('xb') as stream:
                    while block := source.read(1024 * 1024):
                        stream.write(block)
                    stream.flush(); os.fsync(stream.fileno())
        # Apply directory ownership/modes last, after children; retain exact numeric identities.
        by_depth = sorted(members, key=lambda value: len(PurePosixPath(value).parts), reverse=True)
        for name in by_depth:
            member = members[name]
            destination = target if name == '.' else target / name
            os.chown(destination, member.uid, member.gid, follow_symlinks=False)
            os.chmod(destination, member.mode, follow_symlinks=False)
            if member.isdir():
                sync_directory(destination)
            else:
                with destination.open('rb') as stream:
                    os.fsync(stream.fileno())
    if scan(target) != sorted(rows, key=lambda row: row['name']):
        raise ValueError('RESTORE_READBACK_MISMATCH')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['pack', 'restore'])
    parser.add_argument('--name', required=True)
    parser.add_argument('--expected-schema', required=True)
    parser.add_argument('--owner-uid', type=int, required=True)
    parser.add_argument('--owner-gid', type=int, required=True)
    args = parser.parse_args()
    try:
        alphabet = 'abcdefghijklmnopqrstuvwxyz0123456789_.-'
        if not args.name or any(c not in alphabet for c in args.name):
            raise ValueError('ARCHIVE_NAME_REJECTED')
        if file_hash(Path('/app/deploy/schema_manifest.json')) != args.expected_schema:
            raise ValueError('IMAGE_SCHEMA_MISMATCH')
        bundle = Path('/bundle')
        if args.operation == 'pack':
            pack(Path('/source'), bundle, args.name)
            for suffix in ('.tar', '.json'):
                os.chown(bundle / (args.name + suffix), args.owner_uid, args.owner_gid)
        else:
            report = json.loads((bundle / (args.name + '.json')).read_text())
            path = bundle / (args.name + '.tar')
            if file_hash(path) != report['sha256']:
                raise ValueError('ARCHIVE_HASH_MISMATCH')
            restore(path, report['members'], Path('/target'))
        print('ARCHIVE_OPERATION_COMPLETE')
        return 0
    except Exception:
        print('ARCHIVE_OPERATION_FAILED')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
