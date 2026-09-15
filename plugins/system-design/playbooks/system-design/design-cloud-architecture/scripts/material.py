#!/usr/bin/env python3
"""クラウド構成成果をwrite-doc用素材へ束ねる。"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
from playbook_artifacts import build_material  # noqa: E402
p = argparse.ArgumentParser()
p.add_argument("--grounded", required=True)
p.add_argument("--artifact", required=True)
p.add_argument("--output", required=True)
a = p.parse_args()
build_material("design-cloud-architecture", a.grounded, a.artifact, a.output)
