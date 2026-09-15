#!/usr/bin/env bash
set -euo pipefail
PLAYBOOK_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PACKAGE_ROOT=$(cd "$PLAYBOOK_ROOT/../../.." && pwd)
exec "$PACKAGE_ROOT/scripts/prepare.sh" "$@"
