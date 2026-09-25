#!/usr/bin/env python3
"""クラウドアーキテクチャ資料（cloud-architecture型のMarkdown）の構造契約を検査する。

  python3 scripts/architecture.py check [--upstream <上流資料の絶対path> ...] < <クラウドアーキテクチャ資料の本文（Markdown）>

基準資料: write-doc の公開契約「検査が読む目印」の cloud-architecture。見出しの文言は読まない。読むのは、H1と冒頭の本文段落、
  見出し行が「ID | 内容 | 根拠と状態」の追跡の表（資料に1つ、どの見出しの下でもよい）、`flowchart` で始まる Mermaid ブロック1つ、
  本文全体のID参照だけである。上流資料（--upstream の要求発見・利用負荷モデル・品質要求）が定義するID。
入力: 標準入力の本文、--upstream の上流資料の絶対path（複数可）。一時fileは作らず、保存はwrite-docが行う。
正規化: HTMLコメントを除き、コードブロック外のH2見出しで節へ切る（見出しの文言は比べない）。表のセルの `*` と backtick を除く。
  上流からは表の1列目と `### <ID>: ` で始まる見出しのIDを拾う。
合格述語:
  - H1と、最初のH2より前の本文段落（表・引用・箇条書きで始めない）があり、H2が1つ以上あり、どのH2節も空でない
  - 追跡の表が1つあり、IDが一意で、CON- / NODE- / ADR- / FAIL- / ARC-HYP- / ARC-OQ- か、上流で定義済みの <接頭辞>-HYP- / <接頭辞>-OQ- である
  - 根拠と状態のセルが状態の値をちょうど1つ持ち、IDの種別で許される値である（CON: fact / agreed_decision / hypothesis、
    NODE: agreed_decision / hypothesis / open_question、ADR: agreed_decision / hypothesis、FAIL: agreed_decision / hypothesis / open_question、
    <接頭辞>-HYP-: hypothesis、<接頭辞>-OQ-: open_question）。同じセルが引くIDはすべて到達する
  - NODE- と ADR- の行は、CON- か上流のIDを1つ以上引く。FAIL- の行は NODE- を1つ以上引く
  - agreed_decision の CON- が1つ以上ある
  - `flowchart` で始まる Mermaid ブロックがちょうど1つあり、subgraph と end の数が一致し、追跡の表の全 NODE- が現れ、図の中の NODE- が追跡の表にある
  - 本文（冒頭と図を含む）で引く CON / NODE / ADR / FAIL / ARC-HYP / ARC-OQ と上流の REQ / DRV / WL / DIN / QR / QCON と上流の HYP / OQ がすべて定義済み。
    上流の家族を引きながら --upstream が無ければ不合格
失敗時の診断: 標準エラーに `FAIL: <理由>` を1件。終了code 2。
正例: tests/fixtures/design-cloud-architecture/success.md（--upstream に上流3 fixture。status: unresolved）と、未決を解き ADR を agreed_decision にした写し（status: ready）。
反例: 追跡の表が無いか2つある、IDの重複、ID種別と状態の食い違い、状態が2つあるセル、根拠を引かない NODE / ADR、NODE を引かない FAIL、
  agreed_decision の CON が無い、図が無いか2つある、graph で始まる図、subgraph/end の不対応、図に無い NODE、表に無い図の NODE、上流に無いID。
境界例: 見出しの名前と順序は問わず、ADR の小見出しや節の見出しに結論を入れても通る。NODE_DB のような下線名は図の内部名であり NODE- ではない。
  上流の未決を引き継ぐ行は上流IDをそのまま使う。
意味評価として残す範囲: 利用者が指定したプロバイダーと本文の構成が一致しているか、配置方式の判定、選定と代替案の比較の妥当性、ADR の文脈と帰結、
  障害経路の網羅と縮退の妥当性、図が判断に重要な境界と流れを示しているか、追跡の意味上の正しさ、用語定義の語の使い方。

status は、open_question の行が無く、agreed_decision の ADR- が1つ以上あるとき ready、それ以外は unresolved である。
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
    ids_in,
    mermaid_blocks,
    one_state,
    read_stdin,
    read_upstream,
    strip_markup,
    trace_table,
)

TRACE_COLUMNS = ["ID", "内容", "根拠と状態"]
STATES_BY_FAMILY = {
    "CON": ("fact", "agreed_decision", "hypothesis"),
    "NODE": ("agreed_decision", "hypothesis", "open_question"),
    "ADR": ("agreed_decision", "hypothesis"),
    "FAIL": ("agreed_decision", "hypothesis", "open_question"),
}
LOCAL_ID = re.compile(r"^(?:(CON|ADR|FAIL)-\d{3,}|(NODE)-[A-Z0-9]+(?:-[A-Z0-9]+)*|(ARC)-(HYP|OQ)-\d{3,})$")
UPSTREAM_HYP_OR_OQ = re.compile(r"^[A-Z]{2,}-(HYP|OQ)-\d{3,}$")
LOCAL_FAMILIES = {"NODE", "ADR", "FAIL", "CON", "ARC-HYP", "ARC-OQ"}
UPSTREAM_FAMILIES = {"REQ", "DRV", "REQ-HYP", "REQ-OQ", "WL", "DIN", "WL-HYP", "WL-OQ", "QR", "QCON", "QR-HYP", "QR-OQ"}


def family_of(identifier: str) -> str | None:
    match = LOCAL_ID.fullmatch(identifier)
    if match:
        if match.group(1):
            return match.group(1)
        if match.group(2):
            return "NODE"
        return "HYP" if match.group(4) == "HYP" else "OQ"
    upstream = UPSTREAM_HYP_OR_OQ.fullmatch(identifier)
    if upstream:
        return upstream.group(1)
    return None


def check(body: str, upstream: list[str]) -> dict:
    doc = Document(body)
    doc.check_opening()
    registry = Registry(LOCAL_FAMILIES, UPSTREAM_FAMILIES)
    for path_text in upstream:
        registry.add_upstream(read_upstream(path_text), path_text)

    rows = trace_table(doc, TRACE_COLUMNS)
    kinds: dict[str, str] = {}
    for row in rows:
        identifier = strip_markup(row["ID"])
        kind = family_of(identifier)
        if kind is None:
            fail(f"追跡の表のIDは CON- / NODE- / ADR- / FAIL- / ARC-HYP- / ARC-OQ- か、上流の <接頭辞>-HYP- / <接頭辞>-OQ- でなければなりません: {identifier}")
        if identifier.startswith("ARC-") or kind in STATES_BY_FAMILY:
            registry.define(identifier, "追跡の表")
        else:
            if identifier in kinds:
                fail(f"IDが重複しています: {identifier}")
            registry.resolve(identifier, "追跡の表.ID")
        kinds[identifier] = kind

    states: dict[str, str] = {}
    for row in rows:
        identifier = strip_markup(row["ID"])
        kind = kinds[identifier]
        allowed = STATES_BY_FAMILY.get(kind) or (("hypothesis",) if kind == "HYP" else ("open_question",))
        states[identifier] = one_state(row["根拠と状態"], allowed, f"{identifier}.根拠と状態")
        cited = [item for item in registry.resolve(row["根拠と状態"], f"{identifier}.根拠と状態") if item != identifier]
        if kind in ("NODE", "ADR") and not any(item.startswith("CON-") or item in registry.upstream for item in cited):
            fail(f"{identifier} の根拠と状態は CON- か上流のIDを1つ以上引かなければなりません")
        if kind == "FAIL" and not any(item.startswith("NODE-") for item in cited):
            fail(f"{identifier} の根拠と状態は起点の NODE- を1つ以上引かなければなりません")
        registry.resolve(row["内容"], f"{identifier}.内容")

    agreed_constraints = [identifier for identifier, kind in kinds.items() if kind == "CON" and states[identifier] == "agreed_decision"]
    if not agreed_constraints:
        fail("追跡の表に agreed_decision の CON- がありません")

    diagrams = [block for block in mermaid_blocks(doc.all_lines()) if [line for line in block if line.strip()][:1] and [line for line in block if line.strip()][0].strip().startswith("flowchart")]
    if len(diagrams) != 1:
        fail(f"構成図として flowchart で始まる mermaid ブロックが1つ必要です（見つかったブロック: {len(diagrams)}）")
    source = [line for line in diagrams[0] if line.strip()]
    opened = sum(1 for line in source if line.strip().startswith("subgraph "))
    closed = sum(1 for line in source if line.strip() == "end")
    if opened != closed:
        fail(f"構成図の subgraph と end が対応していません: subgraph={opened}, end={closed}")
    diagram_ids = set(ids_in("\n".join(source)))
    nodes = [identifier for identifier, kind in kinds.items() if kind == "NODE"]
    missing = [identifier for identifier in nodes if identifier not in diagram_ids]
    if missing:
        fail(f"構成図に現れない NODE- があります: {missing}")
    stray = sorted(item for item in diagram_ids if item.startswith("NODE-") and item not in kinds)
    if stray:
        fail(f"構成図の NODE- が追跡の表にありません: {stray}")

    registry.resolve("\n".join(doc.all_lines()), "本文")

    adrs = [identifier for identifier, kind in kinds.items() if kind == "ADR"]
    accepted = [identifier for identifier in adrs if states[identifier] == "agreed_decision"]
    hypotheses = [identifier for identifier, kind in kinds.items() if kind == "HYP"]
    open_rows = [identifier for identifier, state in states.items() if state == "open_question"]
    ready = not open_rows and bool(accepted)
    return {
        "verified": True,
        "document_type": "cloud-architecture",
        "status": "ready" if ready else "unresolved",
        "provider_constraints": agreed_constraints,
        "nodes": nodes,
        "adrs": adrs,
        "accepted_adrs": accepted,
        "failure_paths": [identifier for identifier, kind in kinds.items() if kind == "FAIL"],
        "hypotheses": hypotheses,
        "unresolved_elements": [identifier for identifier in open_rows if kinds[identifier] in STATES_BY_FAMILY],
        "open_questions": [identifier for identifier, kind in kinds.items() if kind == "OQ"],
        "upstream": upstream,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("check",))
    parser.add_argument("--upstream", action="append", default=[], help="上流資料（要求発見・利用負荷・品質要求）の絶対path。複数可")
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
