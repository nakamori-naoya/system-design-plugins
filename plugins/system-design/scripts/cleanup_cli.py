#!/usr/bin/env python3
"""共通cleanup契約のCLI。"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from playbook_cleanup import cleanup
p = argparse.ArgumentParser()
p.add_argument("--manifest", required=True)
p.add_argument("--output", required=True)
p.add_argument("--check-only", action="store_true")
a = p.parse_args()
cleanup(a.manifest, a.output, a.check_only)
