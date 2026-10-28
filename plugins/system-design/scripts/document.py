#!/usr/bin/env python3
"""system-design の検査 script が共有する、保存した資料の構文の検査。

このモジュールは意味を評価しない。読むのは、write-doc の各型の template の「検査が読む目印」にある目印
（H1 と冒頭の本文、H2 の有無、画像のリンクとその先のファイル、Mermaid のブロック）だけで、見出しの文言は読まない。

  - 入力は、保存した資料の絶対パス。画像のリンクは資料の置き場からの相対パスとして解決する。
  - 失敗は ContractError で診断を返し、呼び手が `FAIL: <理由>` を標準エラーへ書いて終了コード 2 にする。
"""

from __future__ import annotations

import re
from pathlib import Path

COMMENT = re.compile(r"<!--.*?-->", re.S)
FENCE = re.compile(r"^```", re.M)
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
DRAWIO_SUFFIX = ".drawio.svg"


class ContractError(ValueError):
    """記法の述語が成り立たないときの診断。意味の良し悪しではない。"""


def fail(message: str) -> None:
    raise ContractError(message)


def read(path_text: str) -> tuple[Path, str]:
    path = Path(path_text)
    if not path.is_absolute():
        fail(f"資料は絶対パスで渡す: {path_text}")
    if not path.is_file():
        fail(f"資料が無い: {path_text}")
    return path, COMMENT.sub("", path.read_text(encoding="utf-8"))


def check(path_text: str, *, leading_diagram: bool) -> dict:
    """資料の構文を検査し、図の一覧を返す。

    合格述語:
      1. 最初の空でない行が H1 で、最初の H2 より前に本文があり、H2 が一つ以上ある
      2. ```mermaid のブロックが無い
      3. 画像のリンクはすべて、資料からの相対パスで実在するファイルを指す。`.drawio.svg` の図は、
         資料の名前から `.md` を除いた名前に `.assets/` を付けたディレクトリにあり、draw.io の定義（mxfile）を埋め込んでいる
      4. leading_diagram のとき、H1 の次の空でない行が `.drawio.svg` の図の画像のリンクである
    """
    path, text = read(path_text)
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines or not re.match(r"^# \S", lines[0]):
        fail("最初の行が H1 ではない")
    h2 = [i for i, line in enumerate(lines) if line.startswith("## ")]
    if not h2:
        fail("H2 が無い")
    if h2[0] < 2:
        fail("最初の H2 より前に本文が無い")
    if re.search(r"^```mermaid\b", text, re.M):
        fail("Mermaid のブロックがある。図は draw.io の .drawio.svg で置く")
    assets = path.parent / (path.name[:-3] + ".assets") if path.name.endswith(".md") else None
    diagrams = []
    for alt, link in IMAGE.findall(text):
        if "://" in link:
            continue
        target = (path.parent / link).resolve()
        if not target.is_file():
            fail(f"図のファイルが無い: {link}")
        if link.endswith(DRAWIO_SUFFIX):
            if assets is None or target.parent != assets.resolve():
                fail(f"図が <資料名>.assets/ に無い: {link}")
            if "mxfile" not in target.read_text(encoding="utf-8", errors="replace"):
                fail(f"図に draw.io の定義が埋め込まれていない: {link}")
            if not alt.strip():
                fail(f"図の代替テキストが空: {link}")
            diagrams.append(link)
    if leading_diagram:
        match = IMAGE.fullmatch(lines[1].strip())
        if not match or not match.group(2).endswith(DRAWIO_SUFFIX):
            fail("題名のすぐ下に .drawio.svg の図が無い")
    return {"verified": True, "diagrams": diagrams}
