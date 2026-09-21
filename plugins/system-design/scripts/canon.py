#!/usr/bin/env python3
"""system-design 4入口が共有する、Markdown資料の構文解析と共通述語。

このmoduleは意味を評価しない。読むのは、write-docのtemplateが定める記法（H2見出しの名前と順序、
`### <ID>: <一文>` の小見出しとそのラベル行、表の見出し行と本文行、`<接頭辞>-<数字>` のID、
根拠状態の機械値）だけである。各入口のscriptはこのmoduleを使って、自分の型に固有の述語を重ねる。

  - 入力は標準入力の本文（UTF-8 Markdown）と、引数で渡された上流基準資料のpathだけ。一時fileは作らない。
  - 失敗は ContractError で診断を返し、呼び手が `FAIL: <理由>` を標準エラーへ書いて終了code 2にする。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HEADING = re.compile(r"^(#{1,6})[ ]+(.+?)[ ]*$")
ID_TOKEN = re.compile(r"(?<![A-Za-z0-9_-])([A-Z]{2,}(?:-[A-Z]{2,})*-\d{3,})(?![A-Za-z0-9_-])")
NODE_TOKEN = re.compile(r"(?<![A-Za-z0-9_-])(NODE-[A-Z0-9]+(?:-[A-Z0-9]+)*)(?![A-Za-z0-9_-])")
NUMBER_WITH_UNIT = re.compile(r"^\d[\d,\.]*\s*[^\d\s].*$")
EVIDENCE_STATES = ("fact", "agreed_decision", "hypothesis", "open_question")
CONFIRMED_STATES = ("fact", "agreed_decision")
LABEL_LINE = re.compile(r"^([^:：]+?)[:：]\s*(.*)$")


class ContractError(ValueError):
    """記法の述語が成り立たないときの診断。意味の良し悪しではない。"""


def fail(message: str) -> None:
    raise ContractError(message)


def read_stdin() -> str:
    if sys.stdin.isatty():
        fail("基準資料の本文を標準入力で渡す")
    body = sys.stdin.read()
    if not body.strip():
        fail("標準入力が空。基準資料の本文を標準入力で渡す")
    return body


def read_upstream(path_text: str) -> str:
    path = Path(path_text)
    if not path.is_absolute():
        fail(f"--upstreamは絶対pathでなければなりません: {path_text}")
    if path.is_symlink() or not path.is_file():
        fail(f"--upstreamはregular fileでなければなりません: {path_text}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        fail(f"--upstreamをUTF-8 Markdownとして読めません: {path_text}: {exc}")
    return ""


def strip_markup(text: str) -> str:
    return re.sub(r"[*`]", "", text).strip()


def strip_comments(body: str) -> str:
    return re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)


class Document:
    """H2で切った節、冒頭段落、全見出し。コードブロック内の`#`は見出しに数えない。"""

    def __init__(self, body: str) -> None:
        self.body = strip_comments(body)
        self.order: list[str] = []
        self.sections: dict[str, list[str]] = {}
        self.intro: list[str] = []
        self.title: str | None = None
        current: str | None = None
        in_code = False
        for line in self.body.splitlines():
            if line.startswith("```"):
                in_code = not in_code
            match = None if in_code else HEADING.match(line)
            if match:
                level, title = len(match.group(1)), match.group(2).strip()
                if level == 1 and self.title is None:
                    self.title = title
                    continue
                if level == 2:
                    if title in self.sections:
                        fail(f"H2見出しが重複しています: {title}")
                    current = title
                    self.order.append(title)
                    self.sections[title] = []
                    continue
            if current is None:
                self.intro.append(line)
            else:
                self.sections[current].append(line)

    def require_sections(self, expected: list[str]) -> None:
        if self.title is None:
            fail("文書題名（H1）がありません")
        if self.order != expected:
            missing = [name for name in expected if name not in self.order]
            extra = [name for name in self.order if name not in expected]
            fail(
                "H2見出しがtemplateの名前と順序に一致しません: "
                f"missing={missing}, extra={extra}, order={self.order}"
            )
        intro_text = [line for line in self.intro if line.strip()]
        if not intro_text:
            fail("冒頭の本文段落がありません（最初のH2より前に本文を書く）")
        first = intro_text[0].lstrip()
        if first.startswith(("|", ">", "- ", "* ", "```")):
            fail("冒頭は本文段落で始める（表・引用・箇条書きではない）")
        for name in expected:
            if not any(line.strip() for line in self.sections[name]):
                fail(f"節が空です: {name}")

    def lines(self, name: str) -> list[str]:
        return self.sections[name]

    def text(self, name: str) -> str:
        return "\n".join(self.sections[name])


def tables(lines: list[str]) -> list[dict]:
    """節内のMarkdown表を {header, rows} の列に分けて返す。区切り行は捨てる。"""
    found: list[dict] = []
    current: dict | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            current = None
            continue
        cells = [strip_markup(part) for part in stripped.strip("|").split("|")]
        if current is None:
            current = {"header": cells, "rows": []}
            found.append(current)
            continue
        if all(set(cell) <= set("-: ") for cell in cells):
            continue
        current["rows"].append(cells)
    return found


def single_table(doc: Document, section: str, columns: list[str]) -> list[dict[str, str]]:
    """節に表がちょうど1つあり、見出し行がtemplateの列と一致し、本文行が1行以上あることを確かめて行を返す。"""
    found = tables(doc.lines(section))
    if len(found) != 1:
        fail(f"節「{section}」には表が1つ必要です（見つかった表: {len(found)}）")
    table = found[0]
    if table["header"] != columns:
        fail(f"節「{section}」の表の列がtemplateと一致しません: expected={columns}, actual={table['header']}")
    if not table["rows"]:
        fail(f"節「{section}」の表に本文行がありません")
    rows: list[dict[str, str]] = []
    for index, cells in enumerate(table["rows"], 1):
        if len(cells) != len(columns):
            fail(f"節「{section}」の表{index}行目の列数が見出しと一致しません: {cells}")
        row = dict(zip(columns, cells))
        for column, value in row.items():
            if not value:
                fail(f"節「{section}」の表{index}行目「{column}」が空です（該当なしは列の指示語を書く）")
        rows.append(row)
    return rows


def subsections(lines: list[str], level: int = 3) -> list[tuple[str, list[str]]]:
    found: list[tuple[str, list[str]]] = []
    current: list[str] | None = None
    in_code = False
    for line in lines:
        if line.startswith("```"):
            in_code = not in_code
        match = None if in_code else HEADING.match(line)
        if match and len(match.group(1)) == level:
            current = []
            found.append((match.group(2).strip(), current))
            continue
        if current is not None:
            current.append(line)
    return found


def id_subsections(doc: Document, section: str, pattern: re.Pattern[str], label: str) -> list[tuple[str, str, list[str]]]:
    """`### <ID>: <一文>` の小見出しを (ID, 一文, 本文行) で返す。IDは pattern に一致する。"""
    found = subsections(doc.lines(section))
    if not found:
        fail(f"節「{section}」に `### <{label}>: <一文>` の小見出しがありません")
    result: list[tuple[str, str, list[str]]] = []
    for title, body in found:
        match = re.match(r"^([A-Z][A-Z0-9-]*?)\s*[:：]\s*(.+)$", strip_markup(title))
        if not match:
            fail(f"節「{section}」の小見出しは `### <{label}>: <一文>` の形でなければなりません: {title}")
        identifier, sentence = match.group(1), match.group(2).strip()
        if pattern.fullmatch(identifier) is None:
            fail(f"節「{section}」の小見出しIDの形式が不正です（{label}）: {identifier}")
        if not sentence:
            fail(f"節「{section}」の小見出しに一文がありません: {identifier}")
        if not any(line.strip() for line in body):
            fail(f"{identifier} の本文が空です")
        result.append((identifier, sentence, body))
    return result


def labeled_lines(body: list[str], identifier: str, required: list[str]) -> dict[str, str]:
    """`<ラベル>: <本文>` の行を集め、必須ラベルが揃い、値が空でないことを確かめる。"""
    values: dict[str, str] = {}
    for line in body:
        stripped = strip_markup(line)
        if not stripped:
            continue
        match = LABEL_LINE.match(stripped)
        if not match:
            continue
        key = match.group(1).strip()
        if key in required:
            if key in values:
                fail(f"{identifier} のラベル行が重複しています: {key}")
            values[key] = match.group(2).strip()
    missing = [key for key in required if key not in values]
    if missing:
        fail(f"{identifier} にラベル行がありません: {missing}")
    empty = [key for key in required if not values[key]]
    if empty:
        fail(f"{identifier} のラベル行が空です: {empty}")
    return values


def ids_in(text: str) -> list[str]:
    found = [match.group(1) for match in ID_TOKEN.finditer(text)]
    found += [match.group(1) for match in NODE_TOKEN.finditer(text)]
    seen: list[str] = []
    for item in found:
        if item not in seen:
            seen.append(item)
    return seen


def family(identifier: str) -> str:
    if identifier.startswith("NODE-"):
        return "NODE"
    return identifier.rsplit("-", 1)[0]


def split_ids(cell: str) -> list[str]:
    """`、` 区切りのセルからIDだけを取り出す。`なし` / `未作成` などの指示語はIDではないので空になる。"""
    return ids_in(cell)


def evidence_states_in(text: str) -> list[str]:
    stripped = strip_markup(text)
    return [state for state in EVIDENCE_STATES if re.search(rf"(?<![a-z_]){state}(?![a-z_])", stripped)]


def one_state(cell: str, allowed: tuple[str, ...], label: str) -> str:
    states = evidence_states_in(cell)
    if len(states) != 1 or states[0] not in allowed:
        fail(f"{label} の根拠状態は {list(allowed)} のどれか1つでなければなりません: {cell}")
    return states[0]


def some_states(cell: str, allowed: tuple[str, ...], label: str) -> list[str]:
    """1つ以上の根拠状態を持ち、そのすべてが allowed に収まる（複数の根拠を持つセル用）。"""
    states = evidence_states_in(cell)
    if not states or any(state not in allowed for state in states):
        fail(f"{label} の根拠状態は {list(allowed)} から1つ以上でなければなりません: {cell}")
    return states


def one_of(cell: str, allowed: tuple[str, ...], label: str) -> str:
    value = strip_markup(cell)
    if value not in allowed:
        fail(f"{label} は {list(allowed)} のどれかでなければなりません: {cell}")
    return value


def number_with_unit(cell: str, label: str, *, placeholders: tuple[str, ...] = ("未決", "非該当")) -> bool:
    """`<数値><単位>` か指示語かを確かめる。指示語なら False、数値なら True を返す。"""
    value = strip_markup(cell)
    if value in placeholders:
        return False
    if NUMBER_WITH_UNIT.match(value) is None:
        fail(f"{label} は `<数値><単位>` または {list(placeholders)} でなければなりません: {cell}")
    return True


class Registry:
    """この基準資料で定義したIDと、上流資料で定義したID。参照到達の正解をここから導く。"""

    def __init__(self, local_families: set[str], upstream_families: set[str]) -> None:
        self.local_families = local_families
        self.upstream_families = upstream_families
        self.local: dict[str, str] = {}
        self.upstream: dict[str, str] = {}
        self.upstream_given = False

    def define(self, identifier: str, where: str) -> None:
        if identifier in self.local:
            fail(f"IDが重複しています: {identifier}（{self.local[identifier]} と {where}）")
        self.local[identifier] = where

    def add_upstream(self, text: str, path_text: str) -> None:
        self.upstream_given = True
        document = Document(text)
        for name in document.order:
            lines = document.lines(name)
            for table in tables(lines):
                for row in table["rows"]:
                    if row:
                        for identifier in ids_in(row[0]):
                            self.upstream.setdefault(identifier, path_text)
            for title, _body in subsections(lines):
                match = re.match(r"^([A-Z][A-Z0-9-]*?)\s*[:：]", strip_markup(title))
                if match:
                    self.upstream.setdefault(match.group(1), path_text)

    def resolve(self, text: str, where: str, *, ignore: set[str] = frozenset()) -> list[str]:
        """text中の、検査対象familyのIDがすべて定義済みであることを確かめ、見つけたIDを返す。"""
        found = ids_in(text)
        for identifier in found:
            group = family(identifier)
            if identifier in ignore:
                continue
            if group in self.local_families:
                if identifier not in self.local and identifier not in self.upstream:
                    fail(f"{where} の参照が未解決です: {identifier}")
            elif group in self.upstream_families:
                if identifier in self.upstream or identifier in self.local:
                    continue
                if not self.upstream_given:
                    fail(f"{where} が上流のID {identifier} を参照していますが、--upstream で上流資料が渡されていません")
                fail(f"{where} の上流参照が未解決です: {identifier}")
        return found

    def local_ids(self, group: str) -> list[str]:
        return [identifier for identifier in self.local if family(identifier) == group]


def terminology_lines(doc: Document, section: str = "用語") -> tuple[str | None, int | None, list[str]]:
    """`用語定義: <絶対path> 版: <整数>` または `用語定義: なし`、続く `推奨用語名: a、b` を読む。"""
    lines = [strip_markup(line) for line in doc.lines(section) if line.strip()]
    if not lines:
        fail("節「用語」が空です")
    head = re.match(r"^用語定義[:：]\s*(.+?)\s*(?:版[:：]\s*(\d+))?$", lines[0])
    if head is None:
        fail("節「用語」の1行目は `用語定義: <絶対path> 版: <整数>` または `用語定義: なし` でなければなりません")
    locator = head.group(1).strip()
    if locator == "なし":
        if head.group(2) is not None:
            fail("`用語定義: なし` に版を書けません")
        return None, None, []
    if head.group(2) is None:
        fail("用語定義を参照するときは `版: <整数>` が必要です")
    version = int(head.group(2))
    if version < 1:
        fail("用語定義の版は1以上の整数でなければなりません")
    if not Path(locator).is_absolute():
        fail(f"用語定義の所在は絶対pathでなければなりません: {locator}")
    terms: list[str] = []
    for line in lines[1:]:
        match = re.match(r"^推奨用語名[:：]\s*(.+)$", line)
        if match:
            terms = [item.strip() for item in re.split(r"[、,]", match.group(1)) if item.strip()]
    if not terms:
        fail("用語定義を参照するときは `推奨用語名: <名>、<名>` の行が必要です")
    if len(set(terms)) != len(terms):
        fail("推奨用語名に重複があります")
    return locator, version, terms


def mermaid_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in lines:
        stripped = line.strip()
        if current is None and stripped.startswith("```mermaid"):
            current = []
            continue
        if current is not None and stripped.startswith("```"):
            blocks.append(current)
            current = None
            continue
        if current is not None:
            current.append(line)
    if current is not None:
        fail("mermaidブロックが閉じていません")
    return blocks
