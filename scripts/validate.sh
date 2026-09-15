#!/usr/bin/env bash
# Scenario: 単一package、4公開skill、runtime metadata、依存境界を一度に検査する
set -uo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/system-design-validation.XXXXXX") || exit 2
trap 'rm -rf "$TMP_ROOT"' EXIT
status=0

python3 "$ROOT/scripts/validate_repository.py" "$ROOT" || status=1
python3 "$ROOT/scripts/validate_repository.py" --self-test "$ROOT" || status=1
python3 "$ROOT/scripts/validate_japanese_prose.py" || status=1

while IFS= read -r script; do
  bash -n "$script" || status=1
done < <(find "$ROOT" -type f -name '*.sh' | sort)

while IFS= read -r script; do
  PYTHONPYCACHEPREFIX="$TMP_ROOT/pycache" python3 -m py_compile "$script" || status=1
done < <(find "$ROOT" -type f -name '*.py' | sort)

while IFS= read -r test; do
  PYTHONPYCACHEPREFIX="$TMP_ROOT/pycache" python3 "$test" || status=1
done < <(find "$ROOT/tests" -maxdepth 1 -type f -name 'test_*.py' | sort)

if [ "$status" -eq 0 ]; then
  echo 'Validation: passed'
else
  echo 'Validation: failed'
fi
exit "$status"
