#!/usr/bin/env python3
"""system-design の検査scriptが共有する、Markdown資料の構文解析と共通述語。

このmoduleは意味を評価しない。読むのは、write-doc の各型の template の「検査が読む目印」にある目印（H1と冒頭の本文、
決まった見出し行を持つ追跡の表、`<接頭辞>-<数字>` のID、根拠状態の値、Mermaidブロック）だけで、
見出しの文言は読まない。型ごとのscriptはこのmoduleを使って、自分の型に固有の述語を重ねる。

  - 入力は標準入力の本文（UTF-8 Markdown）と、引数で渡された上流資料のpathだけ。一時fileは作らない。
  - 失敗は ContractError で診断を返し、呼び手が `FAIL: <理由>` を標準エラーへ書いて終了code 2にする。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HEADING = re.compile(r"^(#{1,6})[ ]+(.+?)[ ]*$")
ID_TOKEN = re.compile(r"(?<![A-Za-z0-9_-])([A-Z]{2,}(?:-[A-Z]{2,})*-\d{3,})(?![A-Za-z0-9_-])")
NODE_TOKEN = re.compile(r"(?<![A-Za-z0-9_-])(NODE-[A-Z0-9]+(?:-[A-Z0-9]+)*)(?![A-Za-z0-9_-])")
EVIDENCE_STATES = ("fact", "agreed_decision", "hypothesis", "open_question")


class ContractError(ValueError):
    """記法の述語が成り立たないときの診断。意味の良し悪しではない。"""


def fail(message: str) -> None:
    raise ContractError(message)


def read_stdin() -> str:
    if sys.stdin.isatty():
        fail("資料の本文を標準入力で渡す")
    body = sys.stdin.read()
    if not body.strip():
        fail("標準入力が空。資料の本文を標準入力で渡す")
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
    """H2で切った節、冒頭段落。コードブロック内の`#`は見出しに数えない。同じ見出しの節は後の節を別の節として保つ。"""

    def __init__(self, body: str) -> None:
        self.body = strip_comments(body)
        self.order: list[str] = []
        self.sections: dict[str, list[str]] = {}
        self.blocks: list[list[str]] = []
        self.intro: list[str] = []
        self.title: str | None = None
        current: list[str] | None = None
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
                    current = []
                    self.blocks.append(current)
                    self.order.append(title)
                    self.sections.setdefault(title, current)
                    continue
            if current is None:
                self.intro.append(line)
            else:
                current.append(line)

    def lines(self, name: str) -> list[str]:
        return self.sections[name]

    def all_lines(self) -> list[str]:
        """冒頭と全H2節の行。見出しの行は含まない。"""
        lines = list(self.intro)
        for block in self.blocks:
            lines.append("")
            lines.extend(block)
        return lines

    def check_opening(self) -> None:
        """H1、最初のH2より前の本文、1つ以上のH2があり、どのH2節も空でない。見出しの文言は見ない。"""
        if self.title is None:
            fail("文書題名（H1）がありません")
        intro_text = [line for line in self.intro if line.strip()]
        if not intro_text:
            fail("冒頭の本文がありません（最初のH2より前に本文を書く）")
        if not self.blocks:
            fail("本文を判断単位へ分けるH2見出しがありません")
        for title, block in zip(self.order, self.blocks):
            if not any(line.strip() for line in block):
                fail(f"節が空です: {title}")


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


def trace_table(doc: Document, columns: list[str], *, required: bool = True) -> list[dict[str, str]]:
    """見出し行が columns と一致する表（追跡の表）を資料全体から探す。どの見出しの下にあってもよい。

    required なら、ちょうど1つあり本文行が1行以上あることを確かめる。無くてよい表は、無ければ空の list を返す。
    各行の列数が見出しと一致し、セルが空でないことを確かめて行を返す。
    """
    found = [table for table in tables(doc.all_lines()) if table["header"] == columns]
    label = " | ".join(columns)
    if len(found) > 1:
        fail(f"「{label}」の表が {len(found)} 個あります（資料に1つだけ置く）")
    if not found:
        if required:
            fail(f"「{label}」の見出し行を持つ追跡の表がありません")
        return []
    table = found[0]
    if not table["rows"]:
        fail(f"「{label}」の表に本文行がありません")
    rows: list[dict[str, str]] = []
    for index, cells in enumerate(table["rows"], 1):
        if len(cells) != len(columns):
            fail(f"「{label}」の表{index}行目の列数が見出しと一致しません: {cells}")
        row = dict(zip(columns, cells))
        for column, value in row.items():
            if not value:
                fail(f"「{label}」の表{index}行目「{column}」が空です")
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


def evidence_states_in(text: str) -> list[str]:
    stripped = strip_markup(text)
    return [state for state in EVIDENCE_STATES if re.search(rf"(?<![a-z_]){state}(?![a-z_])", stripped)]


def one_state(cell: str, allowed: tuple[str, ...], label: str) -> str:
    states = evidence_states_in(cell)
    if len(states) != 1 or states[0] not in allowed:
        fail(f"{label} の根拠状態は {list(allowed)} のどれか1つでなければなりません: {cell}")
    return states[0]


class Registry:
    """検査する資料で定義したIDと、上流資料で定義したID。参照到達の正解をここから導く。"""

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
        for lines in [document.intro, *document.blocks]:
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
