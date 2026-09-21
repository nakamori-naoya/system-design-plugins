#!/usr/bin/env python3
"""クラウドアーキテクチャ資料（cloud-architecture型のMarkdown）の構造契約を検査する。

  python3 scripts/architecture.py check --provider <aws|gcp> [--upstream <上流資料の絶対path> ...] < <クラウドアーキテクチャ資料の本文（Markdown）>

入力は標準入力の本文、利用者が公開入力として明示した `--provider`、`--upstream` で渡した上流資料（要求発見・利用負荷
モデル・品質要求）のpathだけである。一時fileは作らず、保存はwrite-docが行う。通ったときに言えるのは次だけであり、
選定の妥当性やトレードオフの適否は言わない。

  - H2見出しがtemplateの名前と順序に一致し、冒頭に本文段落があり、どの節も空でない
  - `## 設計入力と制約` に、入力providerの根拠となる agreed_decision の CON- がある
  - `## 代替案比較` が12選定項目を各1行持ち、状態が agreed_decision / hypothesis / open_question / not_applicable、
    open_question の行は採用候補が 未決、not_applicable の行は採用候補が 非該当、それ以外は代替案を1つ以上持ち根拠IDが到達する。
    プロバイダー行の採用候補が --provider（AWS / GCP）と一致し、根拠IDに上の CON- を含む
  - `## 採用構成` の NODE- が一意で根拠IDが到達し、`## インフラ構成図` の mermaid ブロック（flowchart で始まり subgraph/end が対応）に全 NODE- が現れる
  - `## ADR` の ADR- が一意で、状態が agreed_decision / hypothesis、根拠IDが到達する
  - `## 障害・縮退経路` の FAIL- が一意で、起点が NODE- へ到達する
  - `## 要求トレーサビリティ` に全 ADR- と全 NODE- が現れ、要求ID・負荷ID・品質要求IDが上流へ到達する
  - `## 仮説と未決` の ID は ARC-HYP- / ARC-OQ-（上流の継続は上流ID）、根拠状態は hypothesis / open_question、検証計画が空でない。
    open_question の代替案比較の行は、根拠IDに `## 仮説と未決` の open_question 行の ID（<接頭辞>-OQ-）を1つ以上引く
  - 本文中の NODE / ADR / FAIL / ARC-HYP / ARC-OQ / CON と上流IDの参照がすべて定義済みである

status は、open_question が無く、代替案比較に open_question の行が無く、agreed_decision の ADR- が1つ以上あるとき ready、
それ以外は unresolved である。
exit 0 = 通った（stdoutに status と ID の一覧のJSON） / 2 = 標準入力が空、--provider が不正、上流が読めない、または述語が
成り立たない（診断は標準エラー `FAIL: <理由>`）。
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
    one_of,
    one_state,
    read_stdin,
    read_upstream,
    single_table,
    some_states,
    strip_markup,
)

SECTIONS = [
    "設計入力と制約",
    "代替案比較",
    "採用構成",
    "ADR",
    "インフラ構成図",
    "障害・縮退経路",
    "要求トレーサビリティ",
    "仮説と未決",
    "この資料に書かないもの",
]
CON = re.compile(r"^CON-\d{3,}$")
NODE = re.compile(r"^NODE-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
ADR = re.compile(r"^ADR-\d{3,}$")
FAILURE = re.compile(r"^FAIL-\d{3,}$")
LOCAL_HYP_OR_OQ = re.compile(r"^ARC-(HYP|OQ)-\d{3,}$")
ANY_HYP_OR_OQ = re.compile(r"^[A-Z]{2,}-(HYP|OQ)-\d{3,}$")
CAPABILITIES = (
    "プロバイダー", "リージョン/AZ", "計算処理", "ネットワーク", "ストレージ", "データベース",
    "メッセージング", "ID管理", "エッジ", "可観測性", "バックアップ/DR", "デリバリー",
)
SELECTION_STATES = ("agreed_decision", "hypothesis", "open_question", "not_applicable")
NODE_STATES = ("agreed_decision", "hypothesis", "open_question")
ADR_STATES = ("agreed_decision", "hypothesis")
PROVIDERS = {"aws": "AWS", "gcp": "GCP"}
LOCAL_FAMILIES = {"NODE", "ADR", "FAIL", "CON", "ARC-HYP", "ARC-OQ"}
UPSTREAM_FAMILIES = {"REQ", "DRV", "REQ-HYP", "REQ-OQ", "WL", "DIN", "WL-HYP", "WL-OQ", "QR", "QCON", "QR-HYP", "QR-OQ"}


def check(body: str, provider: str, upstream: list[str]) -> dict:
    if provider not in PROVIDERS:
        fail(f"--provider は aws または gcp でなければなりません: {provider}")
    doc = Document(body)
    doc.require_sections(SECTIONS)
    registry = Registry(LOCAL_FAMILIES, UPSTREAM_FAMILIES)
    for path_text in upstream:
        registry.add_upstream(read_upstream(path_text), path_text)

    inputs = single_table(doc, "設計入力と制約", ["入力ID", "根拠状態", "内容", "設計への影響"])
    constraint_state: dict[str, str] = {}
    for row in inputs:
        identifier = strip_markup(row["入力ID"])
        if CON.fullmatch(identifier):
            registry.define(identifier, "設計入力と制約")
            constraint_state[identifier] = one_state(row["根拠状態"], ("fact", "agreed_decision", "hypothesis"), identifier)
    nodes = single_table(doc, "採用構成", ["図ノードID", "役割", "採用サービス", "リージョン/AZ・可用性単位", "根拠ID", "状態"])
    for row in nodes:
        identifier = strip_markup(row["図ノードID"])
        if NODE.fullmatch(identifier) is None:
            fail(f"図ノードIDの形式が不正です（NODE-<英大文字・数字>）: {identifier}")
        registry.define(identifier, "採用構成")
    adrs = single_table(doc, "ADR", ["ADR ID", "判断", "候補", "根拠ID", "結果・トレードオフ", "再検討条件", "状態"])
    adr_state: dict[str, str] = {}
    for row in adrs:
        identifier = strip_markup(row["ADR ID"])
        if ADR.fullmatch(identifier) is None:
            fail(f"ADR IDの形式が不正です（ADR-<数字>）: {identifier}")
        registry.define(identifier, "ADR")
        adr_state[identifier] = one_state(row["状態"], ADR_STATES, f"{identifier}.状態")
    failures = single_table(doc, "障害・縮退経路", ["経路ID", "起点", "影響", "縮退", "検知・復旧", "関連ID"])
    for row in failures:
        identifier = strip_markup(row["経路ID"])
        if FAILURE.fullmatch(identifier) is None:
            fail(f"経路IDの形式が不正です（FAIL-<数字>）: {identifier}")
        registry.define(identifier, "障害・縮退経路")
    pending = single_table(doc, "仮説と未決", ["ID", "根拠状態", "内容", "設計感度", "検証計画", "影響先"])
    for row in pending:
        identifier = strip_markup(row["ID"])
        if identifier == "なし":
            continue
        if ANY_HYP_OR_OQ.fullmatch(identifier) is None:
            fail(f"仮説と未決のIDは <接頭辞>-HYP-<数字> または <接頭辞>-OQ-<数字> でなければなりません: {identifier}")
        if LOCAL_HYP_OR_OQ.fullmatch(identifier):
            registry.define(identifier, "仮説と未決")

    for row in inputs:
        identifier = strip_markup(row["入力ID"])
        if not registry.resolve(row["入力ID"], "設計入力と制約.入力ID"):
            fail(f"設計入力と制約の入力IDにIDがありません: {row['入力ID']}")
        if identifier not in constraint_state:
            some_states(row["根拠状態"], ("fact", "agreed_decision", "hypothesis", "open_question"), f"{identifier}.根拠状態")
    agreed_constraints = {identifier for identifier, state in constraint_state.items() if state == "agreed_decision"}
    if not agreed_constraints:
        fail("設計入力と制約に agreed_decision の CON-（入力providerの根拠）がありません")

    alternatives = single_table(doc, "代替案比較", ["選定項目", "採用候補", "代替案", "根拠ID", "利点", "不利・リスク", "状態"])
    seen_capabilities = [one_of(row["選定項目"], CAPABILITIES, "代替案比較.選定項目") for row in alternatives]
    if sorted(seen_capabilities) != sorted(CAPABILITIES):
        fail(f"代替案比較は12選定項目を各1行持たなければなりません: {seen_capabilities}")
    unresolved_capabilities: list[str] = []
    for row in alternatives:
        capability = strip_markup(row["選定項目"])
        state = one_of(row["状態"], SELECTION_STATES, f"代替案比較.{capability}.状態")
        choice = strip_markup(row["採用候補"])
        refs = registry.resolve(row["根拠ID"], f"代替案比較.{capability}.根拠ID")
        if state == "open_question":
            if choice != "未決":
                fail(f"代替案比較.{capability} は open_question なので採用候補は 未決 でなければなりません: {choice}")
            if not any("-OQ-" in item for item in refs):
                fail(f"代替案比較.{capability} は open_question なので根拠IDに決める問い（<接頭辞>-OQ-）が必要です")
            unresolved_capabilities.append(capability)
        elif state == "not_applicable":
            if choice != "非該当":
                fail(f"代替案比較.{capability} は not_applicable なので採用候補は 非該当 でなければなりません: {choice}")
            if strip_markup(row["不利・リスク"]) in ("なし", "—"):
                fail(f"代替案比較.{capability} は not_applicable なので不利・リスクに理由が必要です")
        else:
            if choice in ("未決", "非該当", "なし"):
                fail(f"代替案比較.{capability} は {state} なので採用候補が必要です")
            if strip_markup(row["代替案"]) in ("なし", "—"):
                fail(f"代替案比較.{capability} は比較のため代替案が1つ以上必要です")
            if not refs:
                fail(f"代替案比較.{capability} の根拠IDに到達可能なIDがありません")
        if capability == "プロバイダー":
            if state != "agreed_decision":
                fail("代替案比較.プロバイダー は入力providerの合意なので agreed_decision でなければなりません")
            if choice != PROVIDERS[provider]:
                fail(f"代替案比較.プロバイダー の採用候補が入力provider（{PROVIDERS[provider]}）と一致しません: {choice}")
            if not any(item in agreed_constraints for item in refs):
                fail("代替案比較.プロバイダー の根拠IDに agreed_decision の CON- がありません")

    for row in nodes:
        identifier = strip_markup(row["図ノードID"])
        one_state(row["状態"], NODE_STATES, f"{identifier}.状態")
        if not registry.resolve(row["根拠ID"], f"{identifier}.根拠ID"):
            fail(f"{identifier} の根拠IDに到達可能なIDがありません")

    for row in adrs:
        identifier = strip_markup(row["ADR ID"])
        if not registry.resolve(row["根拠ID"], f"{identifier}.根拠ID"):
            fail(f"{identifier} の根拠IDに到達可能なIDがありません")
        registry.resolve(row["候補"], f"{identifier}.候補")

    blocks = mermaid_blocks(doc.lines("インフラ構成図"))
    if len(blocks) != 1:
        fail(f"インフラ構成図には mermaid ブロックが1つ必要です（見つかったブロック: {len(blocks)}）")
    source = [line for line in blocks[0] if line.strip()]
    if not source or not source[0].strip().startswith("flowchart"):
        fail("インフラ構成図の mermaid は flowchart で始めなければなりません")
    opened = sum(1 for line in source if line.strip().startswith("subgraph "))
    closed = sum(1 for line in source if line.strip() == "end")
    if opened != closed:
        fail(f"インフラ構成図の subgraph と end が対応していません: subgraph={opened}, end={closed}")
    diagram_text = "\n".join(source)
    missing = [strip_markup(row["図ノードID"]) for row in nodes if strip_markup(row["図ノードID"]) not in diagram_text]
    if missing:
        fail(f"インフラ構成図に現れない図ノードがあります: {missing}")

    for row in failures:
        identifier = strip_markup(row["経路ID"])
        origins = registry.resolve(row["起点"], f"{identifier}.起点")
        if not origins or not all(item.startswith("NODE-") for item in origins):
            fail(f"{identifier} の起点は NODE- でなければなりません: {row['起点']}")
        registry.resolve(row["関連ID"], f"{identifier}.関連ID")

    trace = single_table(doc, "要求トレーサビリティ", ["要求ID", "負荷ID", "品質要求ID", "ADR ID", "図ノードID", "検証"])
    traced: set[str] = set()
    for index, row in enumerate(trace, 1):
        for column in ("要求ID", "負荷ID", "品質要求ID", "ADR ID", "図ノードID"):
            traced.update(registry.resolve(row[column], f"要求トレーサビリティ[{index}].{column}"))
    missing = [identifier for identifier in list(adr_state) + registry.local_ids("NODE") if identifier not in traced]
    if missing:
        fail(f"要求トレーサビリティに現れない ADR / 図ノードがあります: {missing}")

    hypotheses: list[str] = []
    open_questions: list[str] = []
    for row in pending:
        identifier = strip_markup(row["ID"])
        if identifier == "なし":
            continue
        state = one_state(row["根拠状態"], ("hypothesis", "open_question"), identifier)
        expected = "-HYP-" if state == "hypothesis" else "-OQ-"
        if expected not in identifier:
            fail(f"{identifier} の根拠状態 {state} はIDの種別と一致しません")
        if not identifier.startswith("ARC-"):
            registry.resolve(identifier, "仮説と未決.ID")
        if strip_markup(row["検証計画"]) in ("なし", "未決", "—"):
            fail(f"{identifier} の検証計画が空です")
        registry.resolve(row["内容"], f"{identifier}.内容")
        registry.resolve(row["影響先"], f"{identifier}.影響先")
        (hypotheses if state == "hypothesis" else open_questions).append(identifier)
    for row in alternatives:
        if strip_markup(row["状態"]) != "open_question":
            continue
        cited = [item for item in ids_in(row["根拠ID"]) if "-OQ-" in item]
        if not any(item in open_questions for item in cited):
            fail(f"代替案比較.{strip_markup(row['選定項目'])} が引く問い {cited} が仮説と未決の open_question 行にありません")

    registry.resolve("\n".join(doc.intro), "冒頭")
    accepted = [identifier for identifier, state in adr_state.items() if state == "agreed_decision"]
    ready = not open_questions and not unresolved_capabilities and bool(accepted)
    return {
        "verified": True,
        "document_type": "cloud-architecture",
        "status": "ready" if ready else "unresolved",
        "provider": provider,
        "provider_constraints": sorted(agreed_constraints),
        "nodes": registry.local_ids("NODE"),
        "adrs": list(adr_state),
        "accepted_adrs": accepted,
        "unresolved_capabilities": unresolved_capabilities,
        "failure_paths": registry.local_ids("FAIL"),
        "hypotheses": hypotheses,
        "open_questions": open_questions,
        "upstream": upstream,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("check",))
    parser.add_argument("--provider", required=True, help="利用者が明示したクラウドプロバイダー（aws または gcp）")
    parser.add_argument("--upstream", action="append", default=[], help="上流資料（要求発見・利用負荷・品質要求）の絶対path。複数可")
    args = parser.parse_args()
    try:
        result = check(read_stdin(), args.provider, args.upstream)
    except ContractError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
