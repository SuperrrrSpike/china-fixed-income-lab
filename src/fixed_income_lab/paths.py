from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEXAR_REPORT_DIR = Path("/Volumes/Lexar_Spike/项目归档/china-fixed-income-lab/reports")


def output_dir() -> Path:
    """Return a writable report directory, preferring explicit config and Lexar."""
    configured = os.environ.get("FIXED_INCOME_OUTPUT_DIR")
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    if LEXAR_REPORT_DIR.parent.parent.parent.exists():
        candidates.append(LEXAR_REPORT_DIR)
    candidates.append(PROJECT_ROOT / "reports")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            probe.touch(exist_ok=True)
            probe.unlink(missing_ok=True)
            return candidate
        except OSError:
            continue
    raise OSError("No writable report directory is available")

