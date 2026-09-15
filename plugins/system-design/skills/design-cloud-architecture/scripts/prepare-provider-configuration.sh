#!/usr/bin/env bash
# 公開requestの外部供給/生成を判定し、共通runtimeへ必要な枝だけを委譲する専用入口。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
RUNTIME="$PACKAGE_ROOT/scripts/prepare.sh"
USAGE='usage: prepare-provider-configuration.sh --request-json <json-object>'

[ "$#" -eq 2 ] && [ "$1" = "--request-json" ] || {
  echo "$USAGE" >&2
  exit 2
}
command -v jq >/dev/null 2>&1 || {
  echo "[error] jq が要る" >&2
  exit 2
}
command -v yq >/dev/null 2>&1 || {
  echo "[error] yq が要る" >&2
  exit 2
}
command -v shasum >/dev/null 2>&1 || {
  echo "[error] shasum が要る" >&2
  exit 2
}

request="$2"
printf '%s' "$request" | jq -e 'type == "object"' >/dev/null 2>&1 || {
  echo "[error] requestがJSON objectではない" >&2
  exit 2
}

if printf '%s' "$request" | jq -e 'has("provider_resolution")' >/dev/null; then
  resolution=$(printf '%s' "$request" | jq -cer '
    .provider_resolution |
    select(type == "object" and (keys | sort) == ["config_fingerprint", "config_locator", "provider"]) |
    select((.provider == "aws" or .provider == "gcp") and
      (.config_locator | type == "string" and startswith("/")) and
      (.config_fingerprint | type == "string" and test("^sha256:[0-9a-f]{64}$")))
  ') || {
    echo "[error] request.provider_resolutionが不完全または不正" >&2
    exit 2
  }
  locator=$(printf '%s' "$resolution" | jq -er '.config_locator')
  [ -f "$locator" ] && [ ! -L "$locator" ] || {
    echo "[error] 外部供給config_locatorがregular fileではない: $locator" >&2
    exit 2
  }
  expected="sha256:$(shasum -a 256 "$locator" | awk '{print $1}')"
  actual=$(printf '%s' "$resolution" | jq -er '.config_fingerprint')
  [ "$actual" = "$expected" ] || {
    echo "[error] 外部供給config_fingerprintがconfig_locatorの内容と一致しない" >&2
    exit 2
  }
  configured_provider=$(yq -er '.cloud.provider' "$locator" 2>/dev/null) || {
    echo "[error] 外部供給config_locatorからcloud.providerを読めない" >&2
    exit 2
  }
  supplied_provider=$(printf '%s' "$resolution" | jq -er '.provider')
  [ "$configured_provider" = "$supplied_provider" ] || {
    echo "[error] 外部供給providerがconfig_locatorのcloud.providerと一致しない" >&2
    exit 2
  }
  jq -cn \
    --argjson resolution "$resolution" \
    '{resolved_provider_configuration:$resolution,
      provider_configuration_ownership:"external_input",
      transient_provider_configuration_path:null}'
  exit 0
fi

target_repository=$(printf '%s' "$request" | jq -er '
  .target_repository |
  select(type == "string" and startswith("/"))
') || {
  echo "[error] provider_resolutionが無いrequestには絶対pathのtarget_repositoryが要る" >&2
  exit 2
}
[ -d "$target_repository" ] || {
  echo "[error] target_repositoryがdirectoryではない: $target_repository" >&2
  exit 2
}
[ -x "$RUNTIME" ] || {
  echo "[error] provider設定runtimeが無い: $RUNTIME" >&2
  exit 2
}

owned_pending=0
resolved_path=""
cleanup_owned_on_exit() {
  original_status=$?
  if [ "$owned_pending" -eq 1 ] && [ -n "$resolved_path" ]; then
    set +e
    cleanup_reason=$(python3 "$PACKAGE_ROOT/scripts/run-config.py" cleanup --config "$resolved_path" 2>&1)
    cleanup_status=$?
    set -e
    if [ "$cleanup_status" -ne 0 ]; then
      printf '[error] provider設定cleanupに失敗: transient_provider_configuration_path=%s provider_configuration_ownership=generated_by_this_skill cleanup_reason=%s\n' \
        "$resolved_path" "$cleanup_reason" >&2
    fi
  fi
  trap - EXIT
  exit "$original_status"
}
trap cleanup_owned_on_exit EXIT
resolved_path=$(bash "$RUNTIME" "$target_repository") || exit 2
owned_pending=1
[ "${resolved_path#/}" != "$resolved_path" ] && [ -f "$resolved_path" ] && [ ! -L "$resolved_path" ] || {
  echo "[error] provider設定runtimeの返却pathが不正: $resolved_path" >&2
  exit 2
}
resolved=$(yq -o=json -I=0 '.' "$resolved_path") || {
  echo "[error] 解決済みprovider設定を読めない: $resolved_path" >&2
  exit 2
}
resolution=$(printf '%s' "$resolved" | jq -cer '
  {provider:.cloud.provider,
   config_locator:.resolution.selected_config,
   config_fingerprint:.resolution.config_fingerprint} |
  select((.provider == "aws" or .provider == "gcp") and
    (.config_locator | type == "string" and startswith("/")) and
    (.config_fingerprint | type == "string" and test("^sha256:[0-9a-f]{64}$")))
') || {
  echo "[error] 解決済みprovider設定の来歴が不完全" >&2
  exit 2
}
locator=$(printf '%s' "$resolution" | jq -er '.config_locator')
[ -f "$locator" ] && [ ! -L "$locator" ] || {
  echo "[error] 選択元provider設定がregular fileではない: $locator" >&2
  exit 2
}
expected="sha256:$(shasum -a 256 "$locator" | awk '{print $1}')"
actual=$(printf '%s' "$resolution" | jq -er '.config_fingerprint')
[ "$actual" = "$expected" ] || {
  echo "[error] 解決済みconfig_fingerprintが選択元の内容と一致しない" >&2
  exit 2
}
result=$(jq -cn \
  --argjson resolution "$resolution" \
  --arg resolved_path "$resolved_path" \
  '{resolved_provider_configuration:$resolution,
    provider_configuration_ownership:"generated_by_this_skill",
    transient_provider_configuration_path:$resolved_path}')
owned_pending=0
trap - EXIT
printf '%s\n' "$result"
