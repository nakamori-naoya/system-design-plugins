#!/usr/bin/env bash
# Resolve exactly one complete config in this precedence order:
# scope, repository local, repository, personal, bundled contract.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
command -v yq >/dev/null 2>&1 || { echo "[error] yq が要る" >&2; exit 2; }
command -v jq >/dev/null 2>&1 || { echo "[error] jq が要る" >&2; exit 2; }

manifest="$PLUGIN_ROOT/.claude-plugin/plugin.json"
name=$(jq -er '.name // empty' "$manifest" 2>/dev/null) \
  || { echo "[error] plugin nameを解決できない: $manifest" >&2; exit 2; }

repo=""
scope_root=""
explain=0
for argument in "$@"; do
  case "$argument" in
    --explain) explain=1 ;;
    --scope=*) scope_root="${argument#--scope=}" ;;
    --*) echo "[error] 未知のoption: $argument" >&2; exit 2 ;;
    *) [ -z "$repo" ] || { echo "[error] repoは1つだけ指定する" >&2; exit 2; }; repo="$argument" ;;
  esac
done
repo="${repo:-$PWD}"
[ -d "$repo" ] || { echo "[error] repo directoryが無い: $repo" >&2; exit 2; }
root=$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null || (cd "$repo" && pwd)) || exit 2

defaults="$PLUGIN_ROOT/config/defaults.yml"
[ -f "$defaults" ] || { echo "[error] 同梱設定契約が無い: $defaults" >&2; exit 2; }
personal="${XDG_CONFIG_HOME:-$HOME/.config}/harness-plugins/${name}.config.yml"
project="$root/.harness-plugins/${name}.config.yml"
local_cfg="$root/.harness-plugins/${name}.local.yml"
selected="$defaults"
source="bundled"
[ ! -f "$personal" ] || { selected="$personal"; source="personal"; }
[ ! -f "$project" ] || { selected="$project"; source="project"; }
[ ! -f "$local_cfg" ] || { selected="$local_cfg"; source="local"; }
if [ -n "$scope_root" ]; then
  if [ -d "$scope_root" ]; then
    for candidate in "$scope_root"/*; do
      [ -f "$candidate" ] || continue
      case "$(basename "$candidate")" in
        *.config.yml) ;;
        *) echo "[error] scope設定の名前が不正: $candidate" >&2; exit 2 ;;
      esac
    done
  fi
  scope_cfg="$scope_root/${name}.config.yml"
  [ ! -f "$scope_cfg" ] || { selected="$scope_cfg"; source="scope"; }
fi

merged=$(yq -o=json -I=0 '.' "$selected" 2>/dev/null) \
  || { echo "[error] YAMLが壊れている: $selected" >&2; exit 2; }
required=$(yq -o=json -I=0 '.' "$defaults") || exit 2
missing=$(jq -rn --argjson req "$required" --argjson got "$merged" '
  def leaves($v;$p): if ($v|type)=="object" then [$v|to_entries[]|leaves(.value;$p+[.key])[]] else [$p] end;
  [$req|leaves(.;[])[] as $p|select($got|getpath($p)==null)|$p|join(".")]|join(", ")')
[ -z "$missing" ] || { echo "[error] 選択した設定が自己完結していない: ${selected}（不足: ${missing}）" >&2; exit 2; }
unknown=$(jq -rn --argjson req "$required" --argjson got "$merged" '
  [$got|paths]|map(select(all(.[];type=="string")))|
  map(. as $p|select($req|getpath($p)==null)|$p|join("."))|join(", ")')
[ -z "$unknown" ] || { echo "[error] 同梱設定契約に無い設定: $unknown" >&2; exit 2; }

[ "$explain" = 0 ] || echo "# 選択した設定: $source ($selected)" >&2
out="$merged"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/finalize.sh"
printf '%s\n' "$out" | yq -P
