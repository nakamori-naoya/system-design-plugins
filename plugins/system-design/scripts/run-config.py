#!/usr/bin/env python3
"""Create and clean one run-scoped resolved configuration."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["create", "cleanup"])
    parser.add_argument("--config")
    parser.add_argument("--root")
    args, remainder = parser.parse_known_args()
    if args.command == "cleanup":
        path = Path(args.config or "").absolute()
        if path.name != "resolved.yml" or path.parent.is_symlink() or path.is_symlink():
            raise ValueError("invalid run config path")
        metadata = path.parent / "run.json"
        info = json.loads(metadata.read_text(encoding="utf-8"))
        expected = {"schema": 1, "config": str(path), "uid": os.getuid()}
        if info != expected or metadata.is_symlink():
            raise ValueError("run ownership mismatch")
        if {item.name for item in path.parent.iterdir()} - {"resolved.yml", "run.json"}:
            raise ValueError("unexpected run files; refusing cleanup")
        path.unlink(missing_ok=True)
        metadata.unlink()
        path.parent.rmdir()
        return

    root = Path(args.root or "").resolve(strict=True)
    directory = Path(tempfile.mkdtemp(prefix="harness-run-")).resolve()
    path = directory / "resolved.yml"
    try:
        arguments = remainder[1:] if remainder[:1] == ["--"] else remainder
        with path.open("w", encoding="utf-8") as output:
            result = subprocess.run(
                ["bash", str(root / "scripts/resolve.sh"), *arguments],
                stdout=output,
                check=False,
            )
        if result.returncode or not path.stat().st_size:
            raise ValueError("config resolution failed")
        path.chmod(0o600)
        metadata = directory / "run.json"
        metadata.write_text(
            json.dumps({"schema": 1, "config": str(path), "uid": os.getuid()}),
            encoding="utf-8",
        )
        metadata.chmod(0o600)
        print(path)
    except BaseException:
        shutil.rmtree(directory)
        raise


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(2)
