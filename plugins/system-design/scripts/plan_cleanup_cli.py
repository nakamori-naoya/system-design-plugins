#!/usr/bin/env python3
"""宣言済み所有対象からcleanup manifestを作るCLI。"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from playbook_cleanup import plan
p = argparse.ArgumentParser()
p.add_argument("--run-root", required=True)
p.add_argument("--output", required=True)
p.add_argument("--owned", action="append", default=[])
p.add_argument("--preserve", action="append", default=[])
a = p.parse_args()
plan(a.run_root, a.output, a.owned, a.preserve)
