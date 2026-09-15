#!/usr/bin/env bash
set -euo pipefail
[ "$#" -ge 0 ] && [ "$#" -le 3 ] || { echo "usage: finalize.sh [resolved.yml [cleanup-manifest cleanup-report]]" >&2; exit 2; }
[ "$#" -ne 2 ] || { echo "usage: finalize.sh <resolved.yml> [cleanup-manifest cleanup-report]" >&2; exit 2; }
PLAYBOOK_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PACKAGE_ROOT=$(cd "$PLAYBOOK_ROOT/../../.." && pwd)
if [ "$#" -eq 0 ]; then
  printf '{"cleanup":"完了","provider_config":"未作成"}\n'
  exit 0
fi
if [ "$#" -eq 3 ]; then
  python3 "$PLAYBOOK_ROOT/scripts/cleanup.py" --manifest "$2" --output "$3" --check-only
fi
python3 "$PACKAGE_ROOT/scripts/run-config.py" cleanup --config "$1"
if [ "$#" -eq 3 ]; then
  python3 "$PLAYBOOK_ROOT/scripts/cleanup.py" --manifest "$2" --output "$3"
fi
printf '{"cleanup":"完了","provider_config":"削除済み"}\n'
