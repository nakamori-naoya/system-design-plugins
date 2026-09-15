#!/usr/bin/env bash
# Validate the system-design setting contract and expose its provenance.
expected_keys=$(jq -c 'keys|sort' <<<"$merged")
[ "$expected_keys" = '["cloud","instructions","version"]' ] \
  || { echo "[error] top-level設定keysが不正" >&2; exit 2; }
jq -e '
  .version == 1 and
  (.cloud|keys == ["provider"]) and
  (.instructions|keys == ["architecture"]) and
  (.instructions.architecture|keys == ["directive"]) and
  (.instructions.architecture.directive|type == "string" and length > 0)
' >/dev/null <<<"$merged" || { echo "[error] system-design設定schemaが不正" >&2; exit 2; }
provider=$(jq -r '.cloud.provider' <<<"$merged")
case "$provider" in
  aws|gcp) ;;
  '') echo "[error] cloud.providerが未指定。awsまたはgcpを設定する" >&2; exit 2 ;;
  *) echo "[error] cloud.providerが不正: ${provider}（awsまたはgcpのみ）" >&2; exit 2 ;;
esac
command -v shasum >/dev/null 2>&1 \
  || { echo "[error] shasum が要る" >&2; exit 2; }
config_fingerprint="sha256:$(shasum -a 256 "$selected" | awk '{print $1}')"

out=$(jq -cn \
  --arg provider "$provider" \
  --arg config_source "$source" \
  --arg selected_config "$selected" \
  --arg repo_root "$root" \
  --arg plugin_root "$PLUGIN_ROOT" \
  --arg config_fingerprint "$config_fingerprint" \
  --argjson instructions "$(jq -c '.instructions' <<<"$merged")" \
  '{schema_version:1, cloud:{provider:$provider}, instructions:$instructions,
    resolution:{config_source:$config_source, selected_config:$selected_config,
      config_fingerprint:$config_fingerprint},
    repo_root:$repo_root, plugin_root:$plugin_root}')
