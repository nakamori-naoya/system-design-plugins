#!/usr/bin/env python3
"""要件（requirements-discovery 型）と非機能要件（non-functional-requirements 型）の資料の構文を検査する。

  python3 scripts/check.py <requirements-discovery|non-functional-requirements> <保存した資料の絶対パス>

基準資料: write-doc の両型の template にある「検査が読む目印」。見出しの文言は読まない。
入力: 型の名前と、保存した資料の絶対パス。
合格述語: package 共有の document.check の述語（H1 と冒頭の本文と H2、Mermaid が無い、図のファイルが
  <資料名>.assets/ に実在し draw.io の定義を埋め込んでいる）。非機能要件は、題名のすぐ下に守る順位の図がある。
失敗時の診断: 標準エラーに `FAIL: <理由>` を1件。終了コード 2。
正例: tests/fixtures/requirements-discovery.md、tests/fixtures/non-functional-requirements.md。
反例: tests/test_check.py の負例（H1 が無い、冒頭の本文が無い、Mermaid、無い図、定義を埋め込んでいない図、
  別の置き場の図、題名の下に図の無い非機能要件）。
意味評価として残す範囲: 要件と手段の分け方、事実と決定と推定と未決の書き分け、数値の出し方と時間窓、
  守る順位の妥当性、図が本文と同じことを示しているか、二つの資料に同じ値を写していないか。
exit 0 = 通った（標準出力に JSON） / 2 = 述語が成り立たない。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from document import ContractError, check  # noqa: E402  package 共有の構文の検査

TYPES = {"requirements-discovery": False, "non-functional-requirements": True}


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in TYPES:
        print("usage: check.py <requirements-discovery|non-functional-requirements> <資料の絶対パス>", file=sys.stderr)
        return 2
    try:
        result = check(sys.argv[2], leading_diagram=TYPES[sys.argv[1]])
    except (ContractError, OSError, UnicodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
