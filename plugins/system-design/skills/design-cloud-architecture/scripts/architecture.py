#!/usr/bin/env python3
"""インフラ構成（cloud-architecture 型）の資料の構文を検査する。

  python3 scripts/architecture.py <保存した資料の絶対パス>

基準資料: write-doc の cloud-architecture 型の template にある「検査が読む目印」。見出しの文言は読まない。
入力: 保存した資料の絶対パス。
合格述語: package 共有の document.check の述語（H1 と冒頭の本文と H2、Mermaid が無い、図のファイルが
  <資料名>.assets/ に実在し draw.io の定義を埋め込んでいる）に加え、題名のすぐ下に構成図がある。
失敗時の診断: 標準エラーに `FAIL: <理由>` を1件。終了コード 2。
正例: tests/fixtures/cloud-architecture.md。
反例: tests/test_check.py の負例（題名の下に構成図が無い、Mermaid の構成図、無い図、定義を埋め込んでいない図）。
意味評価として残す範囲: 利用者が指定したプロバイダーと構成の一致、選んだ理由と比べた候補の妥当性、
  障害時の振る舞い、図が判断に効く境界と流れを示しているか、図と本文の名前の一致。
exit 0 = 通った（標準出力に JSON） / 2 = 述語が成り立たない。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from document import ContractError, check  # noqa: E402  package 共有の構文の検査


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: architecture.py <資料の絶対パス>", file=sys.stderr)
        return 2
    try:
        result = check(sys.argv[1], leading_diagram=True)
    except (ContractError, OSError, UnicodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
