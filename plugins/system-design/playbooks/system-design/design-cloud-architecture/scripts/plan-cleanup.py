#!/usr/bin/env python3
"""後片付け対象を明示したmanifestを作る。"""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parents[4] / "scripts" / "plan_cleanup_cli.py"), run_name="__main__")
