"""Read-only verification of the exact self-hosted browser distribution manifest."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re


def verify(root: Path) -> int:
    manifest = json.loads((root / 'vendor/manifest.json').read_text())
    html = (root / 'index.html').read_text()
    if re.search(r'<script[^>]+src=["\']https?://', html):
        raise ValueError
    packages = manifest['packages']
    if {p['name'] for p in packages} != {'vue', 'marked', 'dompurify'} or len(packages) != 3:
        raise ValueError
    count = 0
    for package in packages:
        if not re.fullmatch(r'\d+\.\d+\.\d+', package['version']):
            raise ValueError
        if not any('LICENSE' in entry['file'] for entry in package['files']):
            raise ValueError
        for entry in package['files']:
            relative = Path(entry['file'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError
            path = root / 'vendor' / relative
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError
            content = path.read_bytes()
            sri = 'sha384-' + base64.b64encode(hashlib.sha384(content).digest()).decode()
            if hashlib.sha256(content).hexdigest() != entry['sha256'] or sri != entry['sri']:
                raise ValueError
            if path.suffix == '.js' and (
                f'src="/ui/vendor/{entry["file"]}" integrity="{sri}"' not in html
            ):
                raise ValueError
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    try:
        count = verify(args.root)
    except (OSError, ValueError, KeyError, TypeError):
        print('FRONTEND_ASSET_CHECK_FAILED')
        return 1
    print(f'PASS: {count} browser distribution/license files; runtime acceptance BLOCKED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
