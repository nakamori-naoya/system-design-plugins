#!/usr/bin/env python3
"""品質要求資料（quality-requirements型のMarkdown）の構造契約を検査する。

  python3 scripts/quality.py check [--upstream <上流資料の絶対path> ...] < <品質要求資料の本文（Markdown）>

基準資料: write-doc の quality-requirements 型の template と見本。本文の見出しは読み手に合わせて名付けてよく、後続資料が
  IDで参照する品質要求と未決は「追跡情報」の節の表に置く。上流（要求発見・利用負荷モデル）の追跡情報が定義するID。
入力: 標準入力の本文と、--upstream の上流資料の絶対path（複数可）。一時fileは作らず、保存はwrite-docが行う。
正規化: HTMLコメントを除き、コードブロック外の見出しで節へ切る。表のセルの `*` と backtick を除く。上流からは表の1列目のIDを拾う。
合格述語:
  - H1と、最初のH2より前の本文段落（表・引用・箇条書きで始めない）があり、H2が1つ以上あり、どのH2節も空でない
  - 「追跡情報」の節に「ID | 守る性質 | 観測・検証 | 根拠と状態」の表があり、IDが QR- / QR-OQ- で一意
  - QR- の根拠と状態が agreed_decision / hypothesis / open_question のどれか一つ、QR-OQ- は open_question
  - 根拠と状態が引く REQ- / DRV- / CON- / WL- / DIN- / 上流の未決が、上流資料で定義済みである
失敗時の診断: 標準エラーに `FAIL: <理由>` を1件。終了code 2。
正例: tests/fixtures/discover-quality-requirements/success.md（write-doc の見本と同じ本文。--upstream に要求発見と利用負荷のfixture）。
反例: 追跡情報の節が無い、IDの形式が違う、根拠と状態の語彙が違う、上流に無いIDを引く。
境界例: 見出しの名前と順序は問わない。未決が無ければ status: ready。
意味評価として残す範囲: 観測点・指標・閾値・時間窓の妥当性、品質区分の網羅、矛盾の扱い、負荷の仮説を合意済みの前提へ変えていないか。

exit 0 = 通った（stdoutに status と ID の一覧のJSON） / 2 = 標準入力が空、上流が読めない、または述語が成り立たない。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from canon import (  # noqa: E402  package共有の構文解析と共通述語
    ContractError,
    Document,
    Registry,
    fail,
    one_state,
    read_stdin,
    read_upstream,
    single_table,
    strip_markup,
)

QR = re.compile(r"^QR-\d{3,}$")
QCON = re.compile(r"^QCON-\d{3,}$")
LOCAL_HYP_OR_OQ = re.compile(r"^QR-(HYP|OQ)-\d{3,}$")
QR_STATES = ("agreed_decision", "hypothesis", "open_question")
LOCAL_FAMILIES = {"QR", "QCON", "QR-HYP", "QR-OQ"}
UPSTREAM_FAMILIES = {"REQ", "DRV", "CON", "REQ-HYP", "REQ-OQ", "WL", "DIN", "WL-HYP", "WL-OQ"}


def check_human_format(doc: Document, registry: Registry, upstream: list[str]) -> dict:
    if doc.title is None:
        fail("文書題名（H1）がありません")
    intro = [line for line in doc.intro if line.strip()]
    if not intro:
        fail("冒頭の本文段落がありません（最初のH2より前に本文を書く）")
    if intro[0].lstrip().startswith(("|", ">", "- ", "* ")):
        fail("冒頭は本文段落で始める（表・引用・箇条書きではない）")
    if not doc.order:
        fail("本文を判断単位へ分けるH2見出しがありません")
    for name in doc.order:
        if not any(line.strip() for line in doc.sections[name]):
            fail(f"節が空です: {name}")
    if "追跡情報" not in doc.sections:
        fail("後続資料へ渡す品質要求の追跡情報がありません")

    rows = single_table(doc, "追跡情報", ["ID", "守る性質", "観測・検証", "根拠と状態"])
    requirements: list[str] = []
    non_open: list[str] = []
    open_questions: list[str] = []
    for row in rows:
        identifier = strip_markup(row["ID"])
        if QR.fullmatch(identifier):
            registry.define(identifier, "追跡情報")
            requirements.append(identifier)
            state = one_state(row["根拠と状態"], QR_STATES, f"{identifier}.根拠と状態")
            if state != "open_question":
                non_open.append(identifier)
        elif LOCAL_HYP_OR_OQ.fullmatch(identifier) and "-OQ-" in identifier:
            registry.define(identifier, "追跡情報")
            one_state(row["根拠と状態"], ("open_question",), f"{identifier}.根拠と状態")
            open_questions.append(identifier)
        else:
            fail(f"追跡情報のIDは QR-<数字> または QR-OQ-<数字> でなければなりません: {identifier}")
        registry.resolve(row["根拠と状態"], f"{identifier}.根拠と状態")

    return {
        "verified": True,
        "document_type": "quality-requirements",
        "status": "unresolved" if open_questions else "ready",
        "quality_requirements": requirements,
        "non_open": non_open,
        "conflicts": [],
        "open_conflicts": [],
        "hypotheses": [],
        "open_questions": open_questions,
        "upstream": upstream,
    }


def check(body: str, upstream: list[str]) -> dict:
    doc = Document(body)
    registry = Registry(LOCAL_FAMILIES, UPSTREAM_FAMILIES)
    for path_text in upstream:
        registry.add_upstream(read_upstream(path_text), path_text)
    return check_human_format(doc, registry, upstream)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("check",))
    parser.add_argument("--upstream", action="append", default=[], help="上流資料（要求発見・利用負荷モデル）の絶対path。複数可")
    args = parser.parse_args()
    try:
        result = check(read_stdin(), args.upstream)
    except ContractError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
