#!/usr/bin/env python3
"""要求発見資料（requirements-discovery型のMarkdown）の構造契約を検査する。

  python3 scripts/requirements.py check < <要求発見資料の本文（Markdown）>

基準資料: write-doc の公開契約「検査が読む目印」の requirements-discovery。見出しの文言は読まない。
  後続資料がIDで参照する要求と未決は、見出し行が決まった追跡の表に置く（どの見出しの下でもよい）。
入力: 標準入力の本文（UTF-8 Markdown）だけ。上流資料は無い。一時fileは作らず、保存はwrite-docが行う。
正規化: HTMLコメントを除き、コードブロック外のH2見出しで節へ切る（見出しの文言は比べない）。表のセルの `*` と backtick を除く。
合格述語:
  - H1と、最初のH2より前の本文段落（表・引用・箇条書きで始めない）があり、H2が1つ以上あり、どのH2節も空でない
  - 見出し行が「ID | 本文で扱う要求 | 根拠」の表が資料に1つあり、IDが REQ- / DRV- / CON- / DEC- のどれかで一意、
    本文で扱う要求と根拠が空でなく、REQ- が1つ以上ある
  - 見出し行が「ID | 状態 | 後続で決める論点」の表があれば（資料に1つまで）、IDが REQ-HYP- / REQ-OQ- で一意、
    状態が REQ-HYP- なら hypothesis、REQ-OQ- なら open_question
失敗時の診断: 標準エラーに `FAIL: <理由>`（節名、ID、列）を1件。終了code 2。
正例: tests/fixtures/discover-requirements/success.md（write-doc の見本と同じ本文。status: unresolved）。
反例: 追跡の表が無いか2つある、IDの形式が違う、IDの重複、根拠が空、REQ- が無い、状態とIDの種別の食い違い、冒頭が表。
境界例: 未決の表が無ければ status: ready。見出しの名前と順序は問わず、追跡の表を置く見出しを改名しても通る。ほかの列の表は検査しない。
意味評価として残す範囲: 要求と根拠の分類が正しいか、見出しと本文が読み手の判断に足りるか、未決の扱いが妥当か。

exit 0 = 通った（stdoutに status と ID の一覧のJSON） / 2 = 標準入力が空、または述語が成り立たない。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from canon import ContractError, Document, fail, read_stdin, strip_markup, trace_table  # noqa: E402

REQUIREMENT_COLUMNS = ["ID", "本文で扱う要求", "根拠"]
ROUTED_COLUMNS = ["ID", "状態", "後続で決める論点"]
LOCAL_ID = re.compile(r"^(REQ|DRV|CON|DEC)-\d{3,}$")
ROUTED_ID = re.compile(r"^REQ-(HYP|OQ)-\d{3,}$")


def check(body: str) -> dict:
    doc = Document(body)
    doc.check_opening()
    requirement_rows = trace_table(doc, REQUIREMENT_COLUMNS)
    routed_rows = trace_table(doc, ROUTED_COLUMNS, required=False)

    seen: set[str] = set()
    ids: dict[str, list[str]] = {"REQ": [], "DRV": [], "CON": [], "DEC": []}
    for row in requirement_rows:
        identifier = strip_markup(row.get("ID", ""))
        match = LOCAL_ID.fullmatch(identifier)
        if not match:
            fail(f"追跡の表のIDは REQ- / DRV- / CON- / DEC- でなければなりません: {identifier}")
        if identifier in seen:
            fail(f"IDが重複しています: {identifier}")
        seen.add(identifier)
        for column in REQUIREMENT_COLUMNS[1:]:
            if not strip_markup(row.get(column, "")):
                fail(f"{identifier} の{column}が空です")
        ids[match.group(1)].append(identifier)
    if not ids["REQ"]:
        fail("追跡の表に REQ- がありません")

    hypotheses: list[str] = []
    open_questions: list[str] = []
    for row in routed_rows:
        identifier = strip_markup(row.get("ID", ""))
        match = ROUTED_ID.fullmatch(identifier)
        if not match:
            fail(f"後続で決める論点のIDは REQ-HYP- / REQ-OQ- でなければなりません: {identifier}")
        if identifier in seen:
            fail(f"IDが重複しています: {identifier}")
        seen.add(identifier)
        state = strip_markup(row.get("状態", ""))
        expected = "hypothesis" if match.group(1) == "HYP" else "open_question"
        if state != expected:
            fail(f"{identifier} の状態は {expected} でなければなりません: {state}")
        if not strip_markup(row.get("後続で決める論点", "")):
            fail(f"{identifier} の後続で決める論点が空です")
        (hypotheses if expected == "hypothesis" else open_questions).append(identifier)

    return {
        "verified": True,
        "document_type": "requirements-discovery",
        "status": "unresolved" if (open_questions or hypotheses) else "ready",
        "requirements": ids["REQ"],
        "derived_requirements": ids["DRV"],
        "design_decisions": ids["DEC"],
        "constraints": ids["CON"],
        "hypotheses": hypotheses,
        "open_questions": open_questions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("check",))
    parser.parse_args()
    try:
        result = check(read_stdin())
    except ContractError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
