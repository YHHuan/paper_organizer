#!/usr/bin/env bash
# keygen.sh - create a local virtual key for a new paper-organizer user
#
# Usage:
#   ./keygen.sh <username>
#
# Examples:
#   ./keygen.sh alice

# Add the printed key to the Railway VIRTUAL_KEYS variable.

set -euo pipefail

USER="${1:?Usage: $0 <username>}"

if command -v openssl >/dev/null 2>&1; then
  SECRET="$(openssl rand -hex 24)"
else
  SECRET="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(24))
PY
)"
fi

echo "User: ${USER}"
echo "Key: sk-po-${USER}-${SECRET}"
echo ""
echo "Add this key to Railway's VIRTUAL_KEYS variable."
