#!/usr/bin/env bash
# Common runtime-config entry point. It returns one run-scoped resolved YAML path.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
USAGE="usage: prepare.sh --root-only | [repo] [--scope=<dir>]"

if [ ! -f "$PLUGIN_ROOT/.claude-plugin/plugin.json" ] && [ ! -f "$PLUGIN_ROOT/.codex-plugin/plugin.json" ]; then
  echo "[error] plugin rootではない: $PLUGIN_ROOT" >&2
  exit 2
fi
if [ "${1:-}" = "--root-only" ]; then
  [ "$#" -eq 1 ] || { echo "$USAGE" >&2; exit 2; }
  printf '%s\n' "$PLUGIN_ROOT"
  exit 0
fi

repo=""
scope_arg=""
for argument in "$@"; do
  case "$argument" in
    --scope=*) scope_arg="$argument" ;;
    -*) echo "$USAGE" >&2; exit 2 ;;
    *) [ -z "$repo" ] || { echo "$USAGE" >&2; exit 2; }; repo="$argument" ;;
  esac
done
repo="${repo:-$PWD}"
[ -d "$repo" ] || { echo "[error] repo directoryが無い: $repo" >&2; exit 2; }
[ -x "$PLUGIN_ROOT/scripts/resolve.sh" ] || { echo "[error] resolverが無い: $PLUGIN_ROOT/scripts/resolve.sh" >&2; exit 2; }

exec python3 "$SCRIPT_DIR/run-config.py" create --root "$PLUGIN_ROOT" -- "$repo" --explain ${scope_arg:+"$scope_arg"}
