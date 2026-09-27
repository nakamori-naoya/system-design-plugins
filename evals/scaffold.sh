#!/usr/bin/env bash
# ケースが共有する準備。空の作業場所へ、お題の要件と業務知識、ケースが上流として使う資料、
# skill が読む別 package のファイルを置く。各ケースの scaffold.sh が、お題のディレクトリと上流の資料の名前を渡して呼ぶ。
# 上流の資料は、鎖の前のケースが作った成果を固定の材料として materials/upstream/ に写したものである。
# 業務の分け方（split.md）は採点役だけが読み、作業場所へは置かない。
# 別 package（write-doc、grill）は隔離環境に入らないので、兄弟 checkout の最新のファイルを写す。
# 兄弟 checkout が無ければ、写しで代用せずに止まる。
set -euo pipefail

[ $# -ge 1 ] || { echo "使い方: bash scaffold.sh <お題のディレクトリ> [上流の資料の名前 ...]" >&2; exit 2; }
TOPIC_DIR=$(cd "$1" && pwd)
shift
EVALS_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPOSITORY=$(cd "$EVALS_DIR/.." && pwd)
WORKSPACE=$(cd "$(dirname "$REPOSITORY")" && pwd)
WRITE_DOC="$WORKSPACE/write-doc-plugins/plugins/write-doc/skills/write-doc"
GRILL="$WORKSPACE/grill-plugins/plugins/grill/skills/grill"

for skill in "$WRITE_DOC" "$GRILL"; do
  [ -f "$skill/SKILL.md" ] || { echo "兄弟 checkout の skill が無い: $skill" >&2; exit 2; }
done

mkdir -p harness out grill-log upstream
cp -R "$TOPIC_DIR/materials/input" input
cp -R "$TOPIC_DIR/materials/business-knowledge" business-knowledge
for name in "$@"; do
  [ -f "$TOPIC_DIR/materials/upstream/$name.md" ] || { echo "上流の資料が無い: $TOPIC_DIR/materials/upstream/$name.md" >&2; exit 2; }
  cp "$TOPIC_DIR/materials/upstream/$name.md" "upstream/$name.md"
done
cp -R "$WRITE_DOC" harness/write-doc
cp -R "$GRILL" harness/grill
