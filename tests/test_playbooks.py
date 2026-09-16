#!/usr/bin/env python3
"""Direct-publication checks for the four self-contained skills."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "plugins/system-design"
IDS = (
    "discover-requirements",
    "discover-workload-model",
    "discover-quality-requirements",
    "design-cloud-architecture",
)


def exercise(package: Path) -> None:
    manifests = [
        json.loads((package / f".{runtime}-plugin/plugin.json").read_text(encoding="utf-8"))
        for runtime in ("codex", "claude")
    ]
    shared = [
        {key: value.get(key) for key in ("name", "version", "skills")}
        | {"harness": value.get("metadata", {}).get("harness")}
        for value in manifests
    ]
    assert shared[0] == shared[1]
    expected = [f"./skills/{identifier}" for identifier in IDS]
    assert manifests[0]["skills"] == expected
    harness = manifests[0]["metadata"]["harness"]
    assert "playbooks" not in harness
    assert "internalPlugins" not in harness
    for identifier in IDS:
        entry = package / "skills" / identifier / "SKILL.md"
        assert entry.is_file()
        assert f"name: {identifier}\n" in entry.read_text(encoding="utf-8")
        assert not any((package / "skills" / identifier).glob(".*-plugin/plugin.json"))


def main() -> None:
    exercise(PACKAGE)
    with tempfile.TemporaryDirectory(prefix="system-design-copy-") as value:
        copied = Path(value) / "system-design"
        shutil.copytree(PACKAGE, copied)
        exercise(copied)
    print("Skills: passed (4 direct entries, matching manifests, copied package)")


if __name__ == "__main__":
    main()
