#!/usr/bin/env python3
"""クラウド構成の所有対象だけを安全に後片付けする。"""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parents[4] / "scripts" / "cleanup_cli.py"), run_name="__main__")
