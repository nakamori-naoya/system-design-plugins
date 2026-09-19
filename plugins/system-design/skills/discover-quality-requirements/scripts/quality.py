#!/usr/bin/env python3
"""品質要求正本（quality-requirements型のMarkdown）の構造契約を検査する。

  python3 scripts/quality.py check [--upstream <上流正本の絶対path> ...] < <正本の本文（Markdown）>

入力は標準入力の本文と、`--upstream` で渡した上流正本（要求発見・利用負荷モデル）のpathだけである。REQ- / DRV- /
CON- / WL- / DIN- と上流の HYP / OQ の参照は上流正本で定義されたIDへ到達しなければならない。一時fileは作らず、保存は
write-docが行う。通ったときに言えるのは次だけであり、閾値の妥当性や矛盾の扱いの適否は言わない。

  - H2見出しがtemplateの名前と順序に一致し、冒頭に本文段落があり、どの節も空でない
  - `## 品質要求` の QR- が一意で、分類が10区分のどれか、根拠状態が agreed_decision / hypothesis / open_question、
    閾値が `<演算子> <数値> <単位>`（open_question の行だけ 未決）で、観測点・指標・時間窓・母集団・検証方法が空でない
  - `## 品質区分の網羅` が10区分を各1行持ち、指定済みは同じ分類の QR- を1つ以上引き、非該当は QR- を引かない、
    未決は理由または品質要求IDに `## 仮説と未決` の open_question 行の ID（<接頭辞>-OQ-）を1つ以上引く
  - `## トレードオフと矛盾` の QCON- が一意で、対立するIDが到達し、状態が open / resolved、open は open_question 行の影響先から参照される
  - `## 仮説と未決` の ID は QR-HYP- / QR-OQ-（上流の継続は上流ID）、根拠状態は hypothesis / open_question、検証計画が空でない
  - `## 追跡` に全 QR- が現れ、要求ID・負荷IDが上流へ到達する
  - 本文中の QR / QCON / QR-HYP / QR-OQ と上流IDの参照がすべて定義済みである（ADR- / NODE- は後続の資料のIDなので検査しない）

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
    ids_in,
    one_of,
    one_state,
    read_stdin,
    read_upstream,
    single_table,
    some_states,
    strip_markup,
)

SECTIONS = [
    "対象と入力根拠",
    "品質要求",
    "品質区分の網羅",
    "トレードオフと矛盾",
    "仮説と未決",
    "追跡",
    "この資料に書かないもの",
]
QR = re.compile(r"^QR-\d{3,}$")
QCON = re.compile(r"^QCON-\d{3,}$")
LOCAL_HYP_OR_OQ = re.compile(r"^QR-(HYP|OQ)-\d{3,}$")
ANY_HYP_OR_OQ = re.compile(r"^[A-Z]{2,}-(HYP|OQ)-\d{3,}$")
THRESHOLD = re.compile(r"^(<=|>=|<|>|=)\s*\d[\d,\.]*\s*\S.*$")
CATEGORIES = ("応答時間", "処理量", "可用性", "整合性", "耐久性", "復旧性", "安全性", "プライバシー", "運用性", "費用")
QR_STATES = ("agreed_decision", "hypothesis", "open_question")
COVERAGE = ("指定済み", "未決", "非該当")
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
    measurable: list[str] = []
    open_questions: list[str] = []
    for row in rows:
        identifier = strip_markup(row["ID"])
        if QR.fullmatch(identifier):
            registry.define(identifier, "追跡情報")
            requirements.append(identifier)
            state = one_state(row["根拠と状態"], QR_STATES, f"{identifier}.根拠と状態")
            if state != "open_question":
                measurable.append(identifier)
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
        "measurable": measurable,
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
    if doc.order != SECTIONS:
        return check_human_format(doc, registry, upstream)
    doc.require_sections(SECTIONS)

    requirements = single_table(
        doc, "品質要求",
        ["品質要求ID", "分類", "観測点", "指標", "閾値", "時間窓", "対象母集団", "検証方法", "根拠状態"],
    )
    category_of: dict[str, str] = {}
    state_of: dict[str, str] = {}
    for row in requirements:
        identifier = strip_markup(row["品質要求ID"])
        if QR.fullmatch(identifier) is None:
            fail(f"品質要求IDの形式が不正です（QR-<数字>）: {identifier}")
        registry.define(identifier, "品質要求")
        category_of[identifier] = one_of(row["分類"], CATEGORIES, f"{identifier}.分類")
        state_of[identifier] = one_state(row["根拠状態"], QR_STATES, f"{identifier}.根拠状態")
    conflicts = single_table(doc, "トレードオフと矛盾", ["ID", "対立するID", "内容", "判断者", "状態"])
    conflict_state: dict[str, str] = {}
    for row in conflicts:
        identifier = strip_markup(row["ID"])
        if identifier == "なし":
            continue
        if QCON.fullmatch(identifier) is None:
            fail(f"矛盾IDの形式が不正です（QCON-<数字>）: {identifier}")
        registry.define(identifier, "トレードオフと矛盾")
        conflict_state[identifier] = one_of(row["状態"], ("open", "resolved"), f"{identifier}.状態")
    pending = single_table(doc, "仮説と未決", ["ID", "根拠状態", "内容", "検証計画", "影響先"])
    for row in pending:
        identifier = strip_markup(row["ID"])
        if identifier == "なし":
            continue
        if ANY_HYP_OR_OQ.fullmatch(identifier) is None:
            fail(f"仮説と未決のIDは <接頭辞>-HYP-<数字> または <接頭辞>-OQ-<数字> でなければなりません: {identifier}")
        if LOCAL_HYP_OR_OQ.fullmatch(identifier):
            registry.define(identifier, "仮説と未決")

    inputs = single_table(doc, "対象と入力根拠", ["入力ID", "根拠状態", "対象", "品質判断への影響"])
    for row in inputs:
        refs = registry.resolve(row["入力ID"], "対象と入力根拠.入力ID")
        if not refs:
            fail(f"対象と入力根拠の入力IDに上流IDがありません: {row['入力ID']}")
        some_states(row["根拠状態"], ("fact", "agreed_decision", "hypothesis", "open_question"), f"{refs[0]}.根拠状態")

    for row in requirements:
        identifier = strip_markup(row["品質要求ID"])
        threshold = strip_markup(row["閾値"])
        state = state_of[identifier]
        if state == "open_question":
            if threshold != "未決":
                fail(f"{identifier} は open_question なので閾値は 未決 でなければなりません: {threshold}")
        elif THRESHOLD.match(threshold) is None:
            fail(f"{identifier} の閾値は `<演算子> <数値> <単位>` でなければなりません（演算子は < <= = >= >）: {threshold}")
        for column in ("観測点", "指標", "時間窓", "対象母集団", "検証方法"):
            if strip_markup(row[column]) in ("なし", "未決", "—") and state != "open_question":
                fail(f"{identifier} の{column}が未確定なので agreed_decision / hypothesis にできません")
        registry.resolve(" ".join(row.values()), identifier)

    coverage = single_table(doc, "品質区分の網羅", ["区分", "判定", "理由", "品質要求ID"])
    seen_categories = [one_of(row["区分"], CATEGORIES, "品質区分の網羅.区分") for row in coverage]
    if sorted(seen_categories) != sorted(CATEGORIES):
        fail(f"品質区分の網羅は10区分を各1行持たなければなりません: {seen_categories}")
    unresolved_categories: list[tuple[str, list[str]]] = []
    for row in coverage:
        category = strip_markup(row["区分"])
        disposition = one_of(row["判定"], COVERAGE, f"品質区分の網羅.{category}.判定")
        refs = registry.resolve(row["品質要求ID"], f"品質区分の網羅.{category}.品質要求ID")
        qr_refs = [item for item in refs if item.startswith("QR-") and "-HYP-" not in item and "-OQ-" not in item]
        if disposition != "非該当" and any(category_of[item] != category for item in qr_refs):
            fail(f"品質区分の網羅.{category} に別の分類の品質要求があります: {qr_refs}")
        if disposition == "指定済み":
            if not qr_refs:
                fail(f"品質区分の網羅.{category} は指定済みなので同じ分類の QR- が1つ以上必要です")
            if all(state_of[item] == "open_question" for item in qr_refs):
                fail(f"品質区分の網羅.{category} は指定済みですが open_question の品質要求しかありません")
        elif disposition == "非該当":
            if qr_refs:
                fail(f"品質区分の網羅.{category} は非該当なので QR- を持てません: {qr_refs}")
            if strip_markup(row["理由"]) in ("なし", "—"):
                fail(f"品質区分の網羅.{category} は非該当なので理由が必要です")
        else:
            if not any("-OQ-" in item for item in refs + registry.resolve(row["理由"], f"品質区分の網羅.{category}.理由")):
                fail(f"品質区分の網羅.{category} は未決なので理由または品質要求IDに決める問い（<接頭辞>-OQ-）が必要です")
            unresolved_categories.append((category, [item for item in refs + ids_in(row["理由"]) if "-OQ-" in item]))
    specified = {category_of[item] for item in category_of if state_of[item] != "open_question"}
    for row in coverage:
        category = strip_markup(row["区分"])
        if strip_markup(row["判定"]) != "指定済み" and category in specified:
            fail(f"品質区分の網羅.{category} は測定可能な品質要求があるので指定済みでなければなりません")

    open_conflicts = {identifier for identifier, state in conflict_state.items() if state == "open"}
    for row in conflicts:
        identifier = strip_markup(row["ID"])
        if identifier == "なし":
            continue
        refs = registry.resolve(row["対立するID"], f"{identifier}.対立するID")
        if len(refs) < 2:
            fail(f"{identifier} の対立するIDは2つ以上必要です: {row['対立するID']}")
        registry.resolve(row["内容"], f"{identifier}.内容")

    hypotheses: list[str] = []
    open_questions: list[str] = []
    referenced_conflicts: set[str] = set()
    for row in pending:
        identifier = strip_markup(row["ID"])
        if identifier == "なし":
            continue
        state = one_state(row["根拠状態"], ("hypothesis", "open_question"), identifier)
        expected = "-HYP-" if state == "hypothesis" else "-OQ-"
        if expected not in identifier:
            fail(f"{identifier} の根拠状態 {state} はIDの種別と一致しません")
        if not identifier.startswith("QR-"):
            registry.resolve(identifier, "仮説と未決.ID")
        if strip_markup(row["検証計画"]) in ("なし", "未決", "—"):
            fail(f"{identifier} の検証計画が空です")
        registry.resolve(row["内容"], f"{identifier}.内容")
        impacts = registry.resolve(row["影響先"], f"{identifier}.影響先")
        if state == "open_question":
            referenced_conflicts.update(item for item in impacts if item.startswith("QCON-"))
        (hypotheses if state == "hypothesis" else open_questions).append(identifier)
    missing = sorted(open_conflicts - referenced_conflicts)
    if missing:
        fail(f"open の矛盾が仮説と未決の open_question 行の影響先から参照されていません: {missing}")
    for category, cited in unresolved_categories:
        if not any(item in open_questions for item in cited):
            fail(f"品質区分の網羅.{category} が引く問い {cited} が仮説と未決の open_question 行にありません")

    trace = single_table(doc, "追跡", ["品質要求ID", "要求ID", "負荷ID", "ADR・図ノードID"])
    traced: set[str] = set()
    for row in trace:
        refs = registry.resolve(row["品質要求ID"], "追跡.品質要求ID")
        qr_refs = [item for item in refs if item in category_of]
        if not qr_refs:
            fail(f"追跡の品質要求IDに QR- がありません: {row['品質要求ID']}")
        traced.update(qr_refs)
        registry.resolve(row["要求ID"], f"{qr_refs[0]}.要求ID")
        registry.resolve(row["負荷ID"], f"{qr_refs[0]}.負荷ID")
    missing = [identifier for identifier in category_of if identifier not in traced]
    if missing:
        fail(f"追跡に現れない品質要求があります: {missing}")

    registry.resolve("\n".join(doc.intro), "冒頭")
    return {
        "verified": True,
        "document_type": "quality-requirements",
        "status": "unresolved" if open_questions or open_conflicts else "ready",
        "quality_requirements": list(category_of),
        "measurable": [identifier for identifier, state in state_of.items() if state != "open_question"],
        "conflicts": sorted(conflict_state),
        "open_conflicts": sorted(open_conflicts),
        "hypotheses": hypotheses,
        "open_questions": open_questions,
        "upstream": upstream,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("check",))
    parser.add_argument("--upstream", action="append", default=[], help="上流正本（要求発見・利用負荷モデル）の絶対path。複数可")
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
