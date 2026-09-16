#!/usr/bin/env python3
"""要求発見正本（requirements-discovery型のMarkdown）の構造契約を検査する。

  python3 scripts/requirements.py check < <正本の本文（Markdown）>

入力は標準入力の本文だけである（要求発見は上流正本を持たない）。一時fileは作らず、保存はwrite-docが行う。
通ったときに言えるのは次だけであり、要求の正しさや十分性は言わない。

  - H2見出しがtemplateの名前と順序に一致し、冒頭に本文段落があり、どの節も空でない
  - `## 根拠` の根拠ID（SRC-）が一意で、根拠状態が fact / agreed_decision / hypothesis のどれか
  - `### REQ-nnn:` は 受益者 / 必要な成果 / 検証方法 / 根拠 の行を持ち、根拠に fact か agreed_decision の SRC を1つ以上引く
  - `### DRV-nnn:` は 特性 / 失敗リスク / 必要な成果 / 設計への影響 / 見直し条件 の行を持ち、特性に SRC を1つ以上引く
  - `### DEC-nnn:` は agreed_decision の SRC か DRV を1つ以上引く
  - `## 固定制約` の CON- は fact / agreed_decision の SRC だけを根拠にする（仮説を制約へ昇格しない）
  - `## スコープ` は 提供価値 / 実装必須 / 設計説明のみ / 対象外 を各1行持つ
  - `## コマンドとクエリ` の 種別 / イベント種別 / 対象 が語彙に収まり、コマンドの成功イベントはコマンドイベント、
    対になる操作は同じ表の操作名か「なし」で相互に参照する（操作名が用語正本にあるかは ../../scripts/terminology.py が検査する）
  - `## 後続設計で決める論点` の ID は REQ-HYP- / REQ-OQ-、根拠状態は hypothesis / open_question、検証計画が空でない
  - `## 観測可能な完了` に全 REQ / DRV が現れる
  - 本文中の SRC / REQ / DRV / DEC / CON / REQ-HYP / REQ-OQ の参照がすべて定義済みである

exit 0 = 通った（stdoutに status と ID の一覧のJSON） / 2 = 標準入力が空、または述語が成り立たない（診断は標準エラー `FAIL: <理由>`）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from canon import (  # noqa: E402  package共有の構文解析と共通述語
    CONFIRMED_STATES,
    ContractError,
    Document,
    Registry,
    fail,
    id_subsections,
    ids_in,
    labeled_lines,
    one_of,
    one_state,
    read_stdin,
    single_table,
    strip_markup,
    terminology_lines,
)

SECTIONS = [
    "サービス特性と導出要件",
    "負荷・偏りの暫定分類",
    "理由付き設計判断",
    "保持期間と期間上限後の定常状態",
    "固定制約",
    "スコープ",
    "コマンドとクエリ",
    "用語",
    "根拠",
    "後続設計で決める論点",
    "観測可能な完了",
]
REQ_OR_DRV = re.compile(r"^(REQ|DRV)-\d{3,}$")
DEC = re.compile(r"^DEC-\d{3,}$")
CON = re.compile(r"^CON-\d{3,}$")
SRC = re.compile(r"^SRC-\d{3,}$")
HYP_OR_OQ = re.compile(r"^REQ-(HYP|OQ)-\d{3,}$")
REQ_LABELS = ["受益者", "必要な成果", "検証方法", "根拠"]
DRV_LABELS = ["特性", "失敗リスク", "必要な成果", "設計への影響", "見直し条件"]
SCOPE_KINDS = ("提供価値", "実装必須", "設計説明のみ", "対象外")
OPERATION_KINDS = ("コマンド", "クエリ", "—")
EVENT_KINDS = ("コマンド", "クエリ", "時間", "システム", "—")
TARGETS = ("対象内", "対象外", "設計説明のみ", "未決")
LOCAL_FAMILIES = {"SRC", "REQ", "DRV", "DEC", "CON", "REQ-HYP", "REQ-OQ"}


def check(body: str) -> dict:
    doc = Document(body)
    doc.require_sections(SECTIONS)
    registry = Registry(LOCAL_FAMILIES, set())

    evidence = single_table(doc, "根拠", ["根拠ID", "出典", "観測時点", "根拠状態"])
    evidence_state: dict[str, str] = {}
    for row in evidence:
        identifier = strip_markup(row["根拠ID"])
        if SRC.fullmatch(identifier) is None:
            fail(f"根拠IDの形式が不正です（SRC-<数字>）: {identifier}")
        registry.define(identifier, "根拠")
        evidence_state[identifier] = one_state(row["根拠状態"], ("fact", "agreed_decision", "hypothesis"), identifier)

    requirements = id_subsections(doc, "サービス特性と導出要件", REQ_OR_DRV, "REQ-ID または DRV-ID")
    for identifier, _sentence, lines in requirements:
        registry.define(identifier, "サービス特性と導出要件")
    decisions = id_subsections(doc, "理由付き設計判断", DEC, "DEC-ID")
    for identifier, _sentence, lines in decisions:
        registry.define(identifier, "理由付き設計判断")
    constraints = single_table(doc, "固定制約", ["制約ID", "制約", "根拠ID・根拠状態", "影響する要件・判断"])
    for row in constraints:
        identifier = strip_markup(row["制約ID"])
        if CON.fullmatch(identifier) is None:
            fail(f"制約IDの形式が不正です（CON-<数字>）: {identifier}")
        registry.define(identifier, "固定制約")
    routed = single_table(doc, "後続設計で決める論点", ["ID", "根拠状態", "論点", "送り先", "守る成果", "検証計画"])
    for row in routed:
        identifier = strip_markup(row["ID"])
        if HYP_OR_OQ.fullmatch(identifier) is None:
            fail(f"後続設計で決める論点のIDは REQ-HYP-<数字> または REQ-OQ-<数字> でなければなりません: {identifier}")
        registry.define(identifier, "後続設計で決める論点")

    def confirmed_sources(text: str, where: str) -> list[str]:
        sources = [item for item in registry.resolve(text, where) if item.startswith("SRC-")]
        return [item for item in sources if evidence_state[item] in CONFIRMED_STATES]

    for identifier, _sentence, lines in requirements:
        if identifier.startswith("REQ-"):
            values = labeled_lines(lines, identifier, REQ_LABELS)
            registry.resolve("\n".join(lines), identifier)
            if not any(item.startswith("SRC-") for item in ids_in(values["根拠"])):
                fail(f"{identifier} の根拠に SRC- がありません")
            if not confirmed_sources(values["根拠"], f"{identifier}.根拠"):
                fail(f"{identifier} が hypothesis の根拠だけで要求になっています（fact / agreed_decision の SRC が必要）")
        else:
            values = labeled_lines(lines, identifier, DRV_LABELS)
            registry.resolve("\n".join(lines), identifier)
            if not any(item.startswith("SRC-") for item in ids_in(values["特性"])):
                fail(f"{identifier} の特性に根拠ID（SRC-）がありません")

    for identifier, _sentence, lines in decisions:
        text = "\n".join(lines)
        refs = registry.resolve(text, identifier)
        agreed = [item for item in refs if item.startswith("SRC-") and evidence_state[item] == "agreed_decision"]
        derived = [item for item in refs if item.startswith("DRV-")]
        if not agreed and not derived:
            fail(f"{identifier} に agreed_decision の根拠（SRC-）も導出要件（DRV-）もありません")

    for row in constraints:
        identifier = strip_markup(row["制約ID"])
        one_state(row["根拠ID・根拠状態"], CONFIRMED_STATES, f"{identifier}.根拠ID・根拠状態")
        sources = [item for item in registry.resolve(row["根拠ID・根拠状態"], identifier) if item.startswith("SRC-")]
        if not sources:
            fail(f"{identifier} の根拠に SRC- がありません")
        for item in sources:
            if evidence_state[item] not in CONFIRMED_STATES:
                fail(f"{identifier} が未確認の根拠 {item} を制約へ昇格しています")
        registry.resolve(row["影響する要件・判断"], f"{identifier}.影響する要件・判断")

    load = single_table(doc, "負荷・偏りの暫定分類", ["分類", "何が起きる負荷か", "根拠にした要件", "負荷モデルで確かめること"])
    for index, row in enumerate(load, 1):
        if not registry.resolve(row["根拠にした要件"], f"負荷・偏りの暫定分類[{index}].根拠にした要件"):
            fail(f"負荷・偏りの暫定分類[{index}] の根拠にした要件に REQ- / DRV- がありません")

    scope = single_table(doc, "スコープ", ["区分", "内容", "根拠ID・根拠状態"])
    kinds = [one_of(row["区分"], SCOPE_KINDS, "スコープ.区分") for row in scope]
    if sorted(kinds) != sorted(SCOPE_KINDS):
        fail(f"スコープの区分は {list(SCOPE_KINDS)} を各1行持たなければなりません: {kinds}")
    for row in scope:
        registry.resolve(row["根拠ID・根拠状態"], f"スコープ.{row['区分']}")
        one_state(row["根拠ID・根拠状態"], ("fact", "agreed_decision", "hypothesis"), f"スコープ.{row['区分']}")

    registry.resolve(doc.text("保持期間と期間上限後の定常状態"), "保持期間と期間上限後の定常状態")

    locator, _version, _preferred = terminology_lines(doc)
    catalog = single_table(doc, "コマンドとクエリ", ["操作", "種別", "成功時に起きるイベント", "イベント種別", "対になる操作", "対象"])
    operations: dict[str, dict[str, str]] = {}
    for row in catalog:
        name = strip_markup(row["操作"])
        if name in operations:
            fail(f"コマンドとクエリの操作名が重複しています: {name}")
        operations[name] = row
    for name, row in operations.items():
        kind = one_of(row["種別"], OPERATION_KINDS, f"{name}.種別")
        event_kind = one_of(row["イベント種別"], EVENT_KINDS, f"{name}.イベント種別")
        event = strip_markup(row["成功時に起きるイベント"])
        one_of(row["対象"], TARGETS, f"{name}.対象")
        if kind == "コマンド" and (event_kind != "コマンド" or event == "なし"):
            fail(f"{name} はコマンドなので成功時のイベントはコマンドイベントでなければなりません")
        if kind == "クエリ" and event_kind not in ("クエリ", "—"):
            fail(f"{name} はクエリなのでイベント種別はクエリまたは — でなければなりません")
        if kind == "—" and event_kind not in ("時間", "システム"):
            fail(f"{name} は操作ではないのでイベント種別は時間またはシステムでなければなりません")
        if event_kind == "—" and event != "なし":
            fail(f"{name} のイベント種別が — なら成功時に起きるイベントは「なし」でなければなりません")
        counterpart = strip_markup(row["対になる操作"])
        if counterpart != "なし":
            if counterpart not in operations:
                fail(f"{name} の対になる操作が同じ表にありません: {counterpart}")
            if strip_markup(operations[counterpart]["対になる操作"]) != name:
                fail(f"{name} と {counterpart} が対になる操作として相互参照されていません")

    hypotheses: list[str] = []
    open_questions: list[str] = []
    for row in routed:
        identifier = strip_markup(row["ID"])
        state = one_state(row["根拠状態"], ("hypothesis", "open_question"), identifier)
        expected = "REQ-HYP-" if state == "hypothesis" else "REQ-OQ-"
        if not identifier.startswith(expected):
            fail(f"{identifier} の根拠状態 {state} はID接頭辞 {expected} と一致しません")
        if not registry.resolve(row["守る成果"], f"{identifier}.守る成果"):
            fail(f"{identifier} の守る成果に REQ- / DRV- がありません")
        if strip_markup(row["検証計画"]) in ("なし", "未決", "—"):
            fail(f"{identifier} の検証計画が空です（誰が何で確かめるかを書く）")
        (hypotheses if state == "hypothesis" else open_questions).append(identifier)

    completion = single_table(doc, "観測可能な完了", ["要件ID", "完了の観測", "観測者・観測点"])
    covered: set[str] = set()
    for index, row in enumerate(completion, 1):
        refs = registry.resolve(row["要件ID"], f"観測可能な完了[{index}].要件ID")
        if not refs:
            fail(f"観測可能な完了[{index}] の要件IDに REQ- / DRV- がありません")
        covered.update(refs)
    missing = [identifier for identifier, _s, _l in requirements if identifier not in covered]
    if missing:
        fail(f"観測可能な完了に現れない要件があります: {missing}")

    registry.resolve("\n".join(doc.intro), "冒頭")
    status = "unresolved" if open_questions else "ready"
    return {
        "verified": True,
        "document_type": "requirements-discovery",
        "status": status,
        "requirements": [identifier for identifier, _s, _l in requirements if identifier.startswith("REQ-")],
        "derived_requirements": [identifier for identifier, _s, _l in requirements if identifier.startswith("DRV-")],
        "design_decisions": [identifier for identifier, _s, _l in decisions],
        "constraints": registry.local_ids("CON"),
        "hypotheses": hypotheses,
        "open_questions": open_questions,
        "terminology": locator,
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
