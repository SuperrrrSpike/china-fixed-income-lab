from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _first_writable(candidates: list[Path]) -> Path:
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            probe.touch(exist_ok=True)
            probe.unlink(missing_ok=True)
            return candidate
        except OSError:
            continue
    raise OSError("No writable project directory is available")


def output_dir() -> Path:
    """Return the configured report directory or the local project default."""
    configured = os.environ.get("FIXED_INCOME_OUTPUT_DIR")
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.append(PROJECT_ROOT / "reports")
    return _first_writable(candidates)


def raw_data_dir() -> Path:
    """Return the configured raw-data cache or the local project default."""
    configured = os.environ.get("FIXED_INCOME_DATA_DIR")
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.append(PROJECT_ROOT / "data" / "raw")
    return _first_writable(candidates)
