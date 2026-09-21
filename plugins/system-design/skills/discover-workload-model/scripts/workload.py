#!/usr/bin/env python3
"""利用負荷モデル資料（workload-model型のMarkdown）の構造契約を検査する。

  python3 scripts/workload.py check [--upstream <要求発見資料の絶対path> ...] < <利用負荷モデル資料の本文（Markdown）>

入力は標準入力の本文と、`--upstream` で渡した上流資料（要求発見）のpathだけである。REQ- / DRV- / CON- /
REQ-HYP- / REQ-OQ- の参照は上流資料で定義されたIDへ到達しなければならない。一時fileは作らず、保存はwrite-docが行う。
通ったときに言えるのは次だけであり、数値の妥当性や採用仮定の適否は言わない。

  - H2見出しがtemplateの名前と順序に一致し、冒頭に本文段落があり、どの節も空でない
  - `### DIN-nnn:` は 根拠 / 採用する仮定 / 適用範囲 / 要件への影響 / 構成への影響 / 見直し条件 の行を持ち、
    根拠は 公開情報 / 実測 / 利用者決定 / 推定 のどれかで始まり（推定以外は SRC- を引く）、適用範囲は3語のどれか、
    要件への影響は REQ- / DRV- / CON- を1つ以上、構成への影響は 容量 / 分割 / 非同期化 / 流量制御 / 保持 / 削除 を1つ以上含む
  - 推定を根拠にした DIN は `## 計算` に式を持つ
  - `## 利用行為と規模` の WL- が一意で、平均率・ピーク率が `<数値><単位>` か 未決 / 非該当、根拠状態と SRC- を持つ
  - 全 WL が `## データ量・保持・増加` に現れ、全 DIN が `## 要件とインフラ判断への接続` に現れる
  - `## 調査根拠` の SRC- が一意で、使った設計入力が DIN- へ到達する
  - `## 見直し条件と未決` の ID は WL-HYP- / WL-OQ-（上流の継続は上流ID）、根拠状態は hypothesis / open_question、検証計画が空でない
  - 本文中の SRC / WL / DIN / WL-HYP / WL-OQ と上流IDの参照がすべて定義済みである

exit 0 = 通った（stdoutに status と ID の一覧のJSON） / 2 = 標準入力が空、上流が読めない、または述語が成り立たない
（診断は標準エラー `FAIL: <理由>`）。
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
    id_subsections,
    ids_in,
    labeled_lines,
    number_with_unit,
    one_state,
    read_stdin,
    read_upstream,
    single_table,
    some_states,
    strip_markup,
    subsections,
    tables,
)

SECTIONS = [
    "採用する仮定",
    "要件とインフラ判断への接続",
    "初期実装で検証する境界",
    "利用行為と規模",
    "分布・偏り・バースト",
    "データ量・保持・増加",
    "計算",
    "調査根拠",
    "見直し条件と未決",
    "この資料に書かないもの",
]
DIN = re.compile(r"^DIN-\d{3,}$")
WL = re.compile(r"^WL-\d{3,}$")
SRC = re.compile(r"^SRC-\d{3,}$")
LOCAL_HYP_OR_OQ = re.compile(r"^WL-(HYP|OQ)-\d{3,}$")
ANY_HYP_OR_OQ = re.compile(r"^[A-Z]{2,}-(HYP|OQ)-\d{3,}$")
DIN_LABELS = ["根拠", "採用する仮定", "適用範囲", "要件への影響", "構成への影響", "見直し条件"]


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
        fail("後続資料へ渡す設計入力の追跡情報がありません")

    rows = single_table(doc, "追跡情報", ["ID", "設計入力", "根拠と状態", "影響する要求・判断"])
    design_inputs: list[str] = []
    workload_items: list[str] = []
    open_questions: list[str] = []
    for row in rows:
        identifier = strip_markup(row["ID"])
        if DIN.fullmatch(identifier):
            registry.define(identifier, "追跡情報")
            design_inputs.append(identifier)
        elif WL.fullmatch(identifier):
            registry.define(identifier, "追跡情報")
            workload_items.append(identifier)
        elif ANY_HYP_OR_OQ.fullmatch(identifier) and "-OQ-" in identifier:
            if identifier.startswith("WL-"):
                registry.define(identifier, "追跡情報")
            else:
                registry.resolve(identifier, "追跡情報.ID")
            open_questions.append(identifier)
        else:
            fail(f"追跡情報のIDは DIN- / WL- / <接頭辞>-OQ- でなければなりません: {identifier}")
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
EVIDENCE_KINDS = ("公開情報", "実測", "利用者決定", "推定")
APPLICABILITY = ("世界規模の参照値", "初期実装の合格値", "局所負荷")
CONCERNS = ("容量", "分割", "非同期化", "流量制御", "保持", "削除")
DECISION_STATES = ("fact", "agreed_decision", "hypothesis", "open_question")
LOCAL_FAMILIES = {"SRC", "WL", "DIN", "WL-HYP", "WL-OQ"}
UPSTREAM_FAMILIES = {"REQ", "DRV", "CON", "REQ-HYP", "REQ-OQ"}


def skew_table(doc: Document, title: str, columns: list[str]) -> list[dict[str, str]]:
    found = [(name, lines) for name, lines in subsections(doc.lines("分布・偏り・バースト")) if name == title]
    if len(found) != 1:
        fail(f"節「分布・偏り・バースト」に `### {title}` が1つ必要です")
    table_list = tables(found[0][1])
    if len(table_list) != 1:
        fail(f"`### {title}` には表が1つ必要です")
    table = table_list[0]
    if table["header"] != columns:
        fail(f"`### {title}` の表の列がtemplateと一致しません: expected={columns}, actual={table['header']}")
    rows: list[dict[str, str]] = []
    for cells in table["rows"]:
        if len(cells) != len(columns):
            fail(f"`### {title}` の表の列数が見出しと一致しません: {cells}")
        row = dict(zip(columns, cells))
        if strip_markup(row[columns[0]]) == "なし":
            continue
        if any(not value for value in row.values()):
            fail(f"`### {title}` の表に空セルがあります: {cells}")
        rows.append(row)
    return rows


def check(body: str, upstream: list[str]) -> dict:
    doc = Document(body)
    registry = Registry(LOCAL_FAMILIES, UPSTREAM_FAMILIES)
    for path_text in upstream:
        registry.add_upstream(read_upstream(path_text), path_text)
    if doc.order != SECTIONS:
        return check_human_format(doc, registry, upstream)
    doc.require_sections(SECTIONS)

    sources = single_table(doc, "調査根拠", ["根拠ID", "出典", "観測時点", "使った設計入力"])
    for row in sources:
        identifier = strip_markup(row["根拠ID"])
        if SRC.fullmatch(identifier) is None:
            fail(f"根拠IDの形式が不正です（SRC-<数字>）: {identifier}")
        registry.define(identifier, "調査根拠")

    inputs = id_subsections(doc, "採用する仮定", DIN, "DIN-ID")
    for identifier, _sentence, _lines in inputs:
        registry.define(identifier, "採用する仮定")
    scale = single_table(doc, "利用行為と規模", ["負荷ID", "利用者・操作・イベント", "母集団", "平均率", "ピーク率", "時間窓", "根拠状態・根拠ID"])
    for row in scale:
        identifier = strip_markup(row["負荷ID"])
        if WL.fullmatch(identifier) is None:
            fail(f"負荷IDの形式が不正です（WL-<数字>）: {identifier}")
        registry.define(identifier, "利用行為と規模")
    revisit = single_table(doc, "見直し条件と未決", ["ID", "根拠状態", "内容", "検証計画", "影響先"])
    for row in revisit:
        identifier = strip_markup(row["ID"])
        if ANY_HYP_OR_OQ.fullmatch(identifier) is None:
            fail(f"見直し条件と未決のIDは <接頭辞>-HYP-<数字> または <接頭辞>-OQ-<数字> でなければなりません: {identifier}")
        if LOCAL_HYP_OR_OQ.fullmatch(identifier):
            registry.define(identifier, "見直し条件と未決")

    for row in sources:
        if not registry.resolve(row["使った設計入力"], f"{strip_markup(row['根拠ID'])}.使った設計入力"):
            fail(f"{strip_markup(row['根拠ID'])} の使った設計入力に DIN- がありません")

    estimated: list[str] = []
    for identifier, _sentence, lines in inputs:
        values = labeled_lines(lines, identifier, DIN_LABELS)
        registry.resolve("\n".join(lines), identifier)
        kind = next((item for item in EVIDENCE_KINDS if values["根拠"].startswith(item)), None)
        if kind is None:
            fail(f"{identifier} の根拠は {list(EVIDENCE_KINDS)} のどれかで始めなければなりません: {values['根拠']}")
        if kind == "推定":
            estimated.append(identifier)
        elif not any(item.startswith("SRC-") for item in ids_in(values["根拠"])):
            fail(f"{identifier} の根拠（{kind}）に出典の SRC- がありません")
        if not any(values["適用範囲"].startswith(item) for item in APPLICABILITY):
            fail(f"{identifier} の適用範囲は {list(APPLICABILITY)} のどれかでなければなりません: {values['適用範囲']}")
        if not any(item.split("-")[0] in ("REQ", "DRV", "CON") for item in ids_in(values["要件への影響"])):
            fail(f"{identifier} の要件への影響に REQ- / DRV- / CON- がありません")
        if not any(item in values["構成への影響"] for item in CONCERNS):
            fail(f"{identifier} の構成への影響は {list(CONCERNS)} を1つ以上含まなければなりません")

    connections = single_table(doc, "要件とインフラ判断への接続", ["設計入力ID", "補完する要件", "拘束する判断", "根拠状態"])
    connected: set[str] = set()
    for row in connections:
        refs = registry.resolve(row["設計入力ID"], "要件とインフラ判断への接続.設計入力ID")
        if not refs or not all(item.startswith("DIN-") for item in refs):
            fail(f"要件とインフラ判断への接続の設計入力IDは DIN- でなければなりません: {row['設計入力ID']}")
        connected.update(refs)
        if not registry.resolve(row["補完する要件"], f"{refs[0]}.補完する要件"):
            fail(f"{refs[0]} の補完する要件に REQ- / DRV- / CON- がありません")
        if not any(item in row["拘束する判断"] for item in CONCERNS):
            fail(f"{refs[0]} の拘束する判断は {list(CONCERNS)} を1つ以上含まなければなりません")
        some_states(row["根拠状態"], DECISION_STATES, f"{refs[0]}.根拠状態")
    missing = [identifier for identifier, _s, _l in inputs if identifier not in connected]
    if missing:
        fail(f"要件とインフラ判断への接続に現れない設計入力があります: {missing}")

    boundaries = single_table(doc, "初期実装で検証する境界", ["設計入力ID", "初期実装の合格値", "超えたときに見直す判断", "検証方法"])
    for row in boundaries:
        refs = registry.resolve(row["設計入力ID"], "初期実装で検証する境界.設計入力ID")
        if not refs:
            fail(f"初期実装で検証する境界の設計入力IDに DIN- がありません: {row['設計入力ID']}")
        if not any(char.isdigit() for char in row["初期実装の合格値"]):
            fail(f"{refs[0]} の初期実装の合格値に数値がありません: {row['初期実装の合格値']}")

    for row in scale:
        identifier = strip_markup(row["負荷ID"])
        for column in ("平均率", "ピーク率"):
            number_with_unit(row[column], f"{identifier}.{column}")
        some_states(row["根拠状態・根拠ID"], DECISION_STATES, f"{identifier}.根拠状態・根拠ID")
        if not any(item.startswith("SRC-") for item in registry.resolve(row["根拠状態・根拠ID"], f"{identifier}.根拠状態・根拠ID")):
            fail(f"{identifier} の根拠状態・根拠IDに SRC- がありません")

    for title, columns in (
        ("操作頻度型", ["負荷ID", "集中する操作", "分布・偏り", "バースト", "設計感度"]),
        ("影響範囲型", ["負荷ID", "増幅する操作", "fan-out", "hot key", "設計感度"]),
    ):
        for row in skew_table(doc, title, columns):
            refs = registry.resolve(row["負荷ID"], f"{title}.負荷ID")
            if not refs or not all(item.startswith("WL-") for item in refs):
                fail(f"`### {title}` の負荷IDは WL- でなければなりません: {row['負荷ID']}")

    retention = single_table(doc, "データ量・保持・増加", ["負荷ID", "データ量", "読み書き比", "通常利用経路からの除外", "物理消去", "増加", "計算根拠"])
    retained: set[str] = set()
    for row in retention:
        refs = registry.resolve(row["負荷ID"], "データ量・保持・増加.負荷ID")
        if not refs or not all(item.startswith("WL-") for item in refs):
            fail(f"データ量・保持・増加の負荷IDは WL- でなければなりません: {row['負荷ID']}")
        retained.update(refs)
        registry.resolve(row["計算根拠"], f"{refs[0]}.計算根拠")
    missing = [strip_markup(row["負荷ID"]) for row in scale if strip_markup(row["負荷ID"]) not in retained]
    if missing:
        fail(f"データ量・保持・増加に現れない負荷項目があります: {missing}")

    calculations = single_table(doc, "計算", ["ID", "定義", "根拠種別", "式", "時間窓", "確度", "再確認条件"])
    calculated: set[str] = set()
    for row in calculations:
        refs = registry.resolve(row["ID"], "計算.ID")
        if not refs or not all(item.split("-")[0] in ("DIN", "WL") for item in refs):
            fail(f"計算のIDは DIN- または WL- でなければなりません: {row['ID']}")
        calculated.update(refs)
        if not any(row["根拠種別"].startswith(item) for item in EVIDENCE_KINDS):
            fail(f"{refs[0]} の根拠種別は {list(EVIDENCE_KINDS)} のどれかで始めなければなりません: {row['根拠種別']}")
        if not row["確度"].startswith(("高", "中", "低")):
            fail(f"{refs[0]} の確度は 高 / 中 / 低 で始めなければなりません: {row['確度']}")
        if strip_markup(row["式"]) in ("なし", "—"):
            fail(f"{refs[0]} の式が空です")
    missing = [identifier for identifier in estimated if identifier not in calculated]
    if missing:
        fail(f"推定を根拠にした設計入力が計算に現れません: {missing}")

    hypotheses: list[str] = []
    open_questions: list[str] = []
    for row in revisit:
        identifier = strip_markup(row["ID"])
        state = one_state(row["根拠状態"], ("hypothesis", "open_question"), identifier)
        expected = "-HYP-" if state == "hypothesis" else "-OQ-"
        if expected not in identifier:
            fail(f"{identifier} の根拠状態 {state} はIDの種別と一致しません")
        if not identifier.startswith("WL-"):
            registry.resolve(identifier, "見直し条件と未決.ID")
        if strip_markup(row["検証計画"]) in ("なし", "未決", "—"):
            fail(f"{identifier} の検証計画が空です")
        registry.resolve(row["内容"], f"{identifier}.内容")
        registry.resolve(row["影響先"], f"{identifier}.影響先")
        (hypotheses if state == "hypothesis" else open_questions).append(identifier)

    registry.resolve("\n".join(doc.intro), "冒頭")
    return {
        "verified": True,
        "document_type": "workload-model",
        "status": "unresolved" if open_questions else "ready",
        "design_inputs": [identifier for identifier, _s, _l in inputs],
        "workload_items": registry.local_ids("WL"),
        "hypotheses": hypotheses,
        "open_questions": open_questions,
        "upstream": upstream,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("check",))
    parser.add_argument("--upstream", action="append", default=[], help="上流資料（要求発見）の絶対path。複数可")
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
