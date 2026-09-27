#!/usr/bin/env bash
# Scenario: 単一package、2公開skill、検査scriptの正例・反例を一度に検査する
set -uo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/system-design-validation.XXXXXX") || exit 2
trap 'rm -rf "$TMP_ROOT"' EXIT
status=0

# package の配置と manifest の検査は兄弟 checkout の harness-tools が持つ。無ければ止まる（fixtureで代用しない）。
TOOLS="$ROOT/../harness-tools/tools"
[ -d "$TOOLS" ] || { echo "[error] 兄弟 checkout harness-tools が無い: $TOOLS" >&2; exit 2; }
python3 "$TOOLS/validate-plugin-repository.py" "$ROOT" || status=1

# repository固有のvalidator（root契約を置き換えない）
python3 "$ROOT/scripts/validate_repository.py" "$ROOT" || status=1
python3 "$ROOT/scripts/validate_repository.py" --self-test "$ROOT" || status=1
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
