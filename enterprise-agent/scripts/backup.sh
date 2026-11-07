#!/bin/bash
# C22 compatibility entry. Planning requires explicit arguments; no deletion/rotation.
# See docs/50-engineering/retained-recovery.md before any isolated runtime execution.
set -euo pipefail
exec python3 -I -B "$(dirname "$0")/recovery.py" "$@"
