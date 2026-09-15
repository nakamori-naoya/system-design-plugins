#!/usr/bin/env python3
"""品質要求素材の状態と引継ぎを検査する。"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
from playbook_artifacts import verify_material  # noqa: E402
p = argparse.ArgumentParser()
p.add_argument("--grounded", required=True)
p.add_argument("--material", required=True)
p.add_argument("--output", required=True)
a = p.parse_args()
verify_material("discover-quality-requirements", a.grounded, a.material, a.output)
