#!/usr/bin/env bash
# ownershipを閉じて判定し、所有する一時設定だけを共通runtimeへ渡す専用入口。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
RUNTIME="$PACKAGE_ROOT/scripts/run-config.py"
USAGE='usage: cleanup-provider-configuration.sh external_input | generated_by_this_skill <owned-resolved-config>'

case "${1:-}" in
  external_input)
    [ "$#" -eq 1 ] || {
      echo "$USAGE" >&2
      exit 2
    }
    printf '%s\n' '{"provider_cleanup_status":"preserved_external_input"}'
    ;;
  generated_by_this_skill)
    [ "$#" -eq 2 ] || {
      echo "$USAGE" >&2
      exit 2
    }
    [ -f "$RUNTIME" ] || {
      echo "[error] provider設定cleanup runtimeが無い: $RUNTIME" >&2
      exit 2
    }
    python3 "$RUNTIME" cleanup --config "$2" || {
      echo "[error] 所有するprovider一時設定のcleanupに失敗" >&2
      exit 2
    }
    printf '%s\n' '{"provider_cleanup_status":"completed"}'
    ;;
  *)
    echo "$USAGE" >&2
    exit 2
    ;;
esac
