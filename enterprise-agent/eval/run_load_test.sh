#!/bin/bash
# C23 reviewed entry: plan-only unless explicit execution and matching approved digest.
# Historical k6 assets remain historical; no Docker fallback, latest image or cleanup.
set -euo pipefail
exec python3 -I -B "$(dirname "$0")/run_capacity.py" "$@"
