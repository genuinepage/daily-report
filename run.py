#!/usr/bin/env python3
"""수집 → 리포트 한 번에. 루틴에서는 `python3 run.py` 하나만 실행하면 된다."""
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
for script in ("collect.py", "report.py"):
    r = subprocess.run([sys.executable, str(ROOT / script)])
    if r.returncode != 0:
        sys.exit(r.returncode)
