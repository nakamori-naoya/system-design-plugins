#!/usr/bin/env python3
"""利用負荷の資料（workload-model型のMarkdown）の構造契約を検査する。

  python3 scripts/workload.py check [--upstream <要件の資料の絶対path> ...] < <利用負荷の資料の本文（Markdown）>

読む目印: write-doc の workload-model 型の template にある「検査が読む目印」。見出しの文言は読まない。後続資料が
  IDで参照する設計入力と未決は、見出し行が「ID | 設計入力 | 根拠と状態 | 影響する要求・判断」の追跡の表に置く（どの見出しの下でもよい）。
  上流（要件の資料）が定義するID。
入力: 標準入力の本文と、--upstream の上流資料の絶対path（複数可）。一時fileは作らず、保存はwrite-docが行う。
正規化: HTMLコメントを除き、コードブロック外のH2見出しで節へ切る（見出しの文言は比べない）。表のセルの `*` と backtick を除く。上流からは表の1列目のIDを拾う。
合格述語:
  - H1と、最初のH2より前の本文があり、H2が1つ以上あり、どのH2節も空でない
  - 見出し行が「ID | 設計入力 | 根拠と状態 | 影響する要求・判断」の表が資料に1つあり、IDが DIN- / WL- / <接頭辞>-OQ- で一意
  - 上流の <接頭辞>-OQ- と、影響する要求・判断が引く REQ- / DRV- / CON- 等の上流IDが、上流資料で定義済みである
失敗時の診断: 標準エラーに `FAIL: <理由>` を1件。終了code 2。
正例: tests/fixtures/workload-model.md（write-doc の見本と同じ本文。--upstream に要件のfixture）。
反例: 追跡の表が無いか2つある、IDの形式が違う、上流に無いIDを引く、--upstream を渡さずに上流IDを引く。
境界例: 見出しの名前と順序は問わず、追跡の表を置く見出しを改名しても通る。未決が無ければ status: ready。
意味評価として残す範囲: 数値と根拠の妥当性、採用する仮定の適否、本文の計算が追跡の表の値と合っているか。

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
    read_stdin,
    read_upstream,
    trace_table,
    strip_markup,
)

DIN = re.compile(r"^DIN-\d{3,}$")
WL = re.compile(r"^WL-\d{3,}$")
SRC = re.compile(r"^SRC-\d{3,}$")
ANY_HYP_OR_OQ = re.compile(r"^[A-Z]{2,}-(HYP|OQ)-\d{3,}$")


def check_document(doc: Document, registry: Registry, upstream: list[str]) -> dict:
    doc.check_opening()
    rows = trace_table(doc, ["ID", "設計入力", "根拠と状態", "影響する要求・判断"])
    design_inputs: list[str] = []
    workload_items: list[str] = []
    open_questions: list[str] = []
    for row in rows:
        identifier = strip_markup(row["ID"])
        if DIN.fullmatch(identifier):
            registry.define(identifier, "追跡の表")
            design_inputs.append(identifier)
        elif WL.fullmatch(identifier):
            registry.define(identifier, "追跡の表")
            workload_items.append(identifier)
        elif ANY_HYP_OR_OQ.fullmatch(identifier) and "-OQ-" in identifier:
            if identifier.startswith("WL-"):
                registry.define(identifier, "追跡の表")
            else:
                registry.resolve(identifier, "追跡の表.ID")
            open_questions.append(identifier)
        else:
            fail(f"追跡の表のIDは DIN- / WL- / <接頭辞>-OQ- でなければなりません: {identifier}")
        registry.resolve(row["影響する要求・判断"], f"{identifier}.影響する要求・判断")

    return {
        "verified": True,
        "document_type": "workload-model",
        "status": "unresolved" if open_questions else "ready",
        "design_inputs": design_inputs,
        "workload_items": workload_items,
        "hypotheses": [],
        "open_questions": open_questions,
        "upstream": upstream,
    }
LOCAL_FAMILIES = {"SRC", "WL", "DIN", "WL-HYP", "WL-OQ"}
UPSTREAM_FAMILIES = {"REQ", "DRV", "CON", "REQ-HYP", "REQ-OQ"}


def check(body: str, upstream: list[str]) -> dict:
    doc = Document(body)
    registry = Registry(LOCAL_FAMILIES, UPSTREAM_FAMILIES)
    for path_text in upstream:
        registry.add_upstream(read_upstream(path_text), path_text)
    return check_document(doc, registry, upstream)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("check",))
    parser.add_argument("--upstream", action="append", default=[], help="上流資料（要件）の絶対path。複数可")
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
