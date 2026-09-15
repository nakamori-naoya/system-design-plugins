#!/usr/bin/env bash
set -euo pipefail
[ "$#" -eq 1 ] || { echo "usage: resolve.sh <resolved.yml>" >&2; exit 2; }
CONFIG=$1
[ -f "$CONFIG" ] || { echo "[error] 解決済み設定が無い: $CONFIG" >&2; exit 2; }
command -v yq >/dev/null 2>&1 || { echo "[error] yq が要る" >&2; exit 2; }
command -v jq >/dev/null 2>&1 || { echo "[error] jq が要る" >&2; exit 2; }
provider=$(yq -r '.cloud.provider' "$CONFIG")
case "$provider" in aws|gcp) ;; *) echo "[error] 解決済みproviderが不正" >&2; exit 2;; esac
resolved_config="$(cd "$(dirname "$CONFIG")" && pwd -P)/$(basename "$CONFIG")"
yq -o=json -I=0 '.' "$CONFIG" | jq -ce --arg resolved_config "$resolved_config" '
  {provider:.cloud.provider,
   config_source:.resolution.config_source,
   selected_config:.resolution.selected_config,
   resolved_config:$resolved_config,
   config_fingerprint:.resolution.config_fingerprint}
  | select(.config_fingerprint|type == "string" and startswith("sha256:"))
' || { echo "[error] 解決済み設定根拠が欠落" >&2; exit 2; }
