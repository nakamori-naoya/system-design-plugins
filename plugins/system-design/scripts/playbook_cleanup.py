#!/usr/bin/env python3
"""playbookが所有する一時成果だけを、全件事前検査後に削除する。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def stop(message: str) -> None:
    raise ValueError(message)


def write_report(path: str, status: str, deleted: list[str], missing: list[str],
                 preserved: list[str], rejected: list[str]) -> None:
    Path(path).write_text(json.dumps({
        "schema_version": 1, "status": status, "deleted": deleted,
        "missing": missing, "preserved": preserved, "rejected": rejected,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_manifest(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {"run_root", "owned_files", "preserve"}:
        stop("cleanup manifest schemaが不正")
    if not isinstance(value["run_root"], str) or not value["run_root"]:
        stop("run_rootが不正")
    for key in ("owned_files", "preserve"):
        if not isinstance(value[key], list) or not all(isinstance(x, str) and x for x in value[key]):
            stop(f"{key}が不正")
    return value


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def cleanup(manifest_path: str, output_path: str, check_only: bool = False) -> None:
    deleted: list[str] = []
    missing: list[str] = []
    preserved: list[str] = []
    rejected: list[str] = []
    try:
        manifest = load_manifest(manifest_path)
        root_raw = Path(manifest["run_root"])
        if not root_raw.is_absolute() or root_raw.is_symlink() or not root_raw.is_dir():
            stop("run_rootはsymlinkでない既存の絶対directoryでなければならない")
        root = root_raw.resolve(strict=True)
        preserve_raw = {Path(value) for value in manifest["preserve"]}
        owned_raw = [Path(value) for value in manifest["owned_files"]]
        if len(owned_raw) != len(set(owned_raw)):
            stop("owned_filesに重複がある")
        for raw in [*preserve_raw, *owned_raw]:
            if not raw.is_absolute():
                stop(f"cleanup pathは絶対pathでなければならない: {raw}")
            if raw == root_raw or not is_within(raw, root_raw):
                stop(f"所有境界外のcleanup pathを拒否: {raw}")
            if raw.is_symlink():
                stop(f"symlinkのcleanupを拒否: {raw}")
            canonical = raw.resolve(strict=False)
            if not is_within(canonical, root):
                stop(f"解決後に所有境界外となるpathを拒否: {raw}")
        preserve_canonical = {value.resolve(strict=False) for value in preserve_raw}
        owned_canonical = {value.resolve(strict=False) for value in owned_raw}
        conflict = preserve_canonical & owned_canonical
        if conflict:
            stop(f"preserve衝突を拒否: {sorted(map(str, conflict))[0]}")
        for raw in preserve_raw:
            preserved.append(str(raw))
        planned: list[Path] = []
        for raw in owned_raw:
            if not os.path.lexists(raw):
                missing.append(str(raw))
                continue
            resolved = raw.resolve(strict=True)
            if not is_within(resolved, root):
                stop(f"解決後に所有境界外となるpathを拒否: {raw}")
            if not raw.is_file():
                stop(f"通常file以外のcleanupを拒否: {raw}")
            planned.append(raw)
        if check_only:
            write_report(output_path, "checked", [], missing, preserved, rejected)
            return
        for raw in planned:
            raw.unlink()
            deleted.append(str(raw))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        rejected.append(str(exc))
        write_report(output_path, "rejected", deleted, missing, preserved, rejected)
        raise SystemExit(f"[error] {exc}")
    write_report(output_path, "completed", deleted, missing, preserved, rejected)


def plan(run_root: str, output_path: str, owned: list[str], preserve: list[str]) -> None:
    value = {"run_root": run_root, "owned_files": owned, "preserve": preserve}
    Path(output_path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
