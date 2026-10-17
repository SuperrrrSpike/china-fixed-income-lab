from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import __version__
from .data import (
    MarketDataset,
    fetch_china_yield_curve,
    fetch_official_chinabond_curve,
    sample_dataset,
)
from .paths import output_dir
from .quality import validate_market_dataset
from .report import write_report_bundle


PIPELINE_SOURCES = {"demo", "official", "akshare"}


@dataclass(frozen=True)
class PipelineResult:
    run_dir: Path
    quality_path: Path
    manifest_path: Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_dataset(
    source: str,
    start: str | None,
    end: str | None,
    force_refresh: bool,
) -> MarketDataset:
    sample = sample_dataset()
    if source == "demo":
        return sample
    if not start or not end:
        raise ValueError("start and end are required for official and akshare sources")
    if source == "official":
        curve = fetch_official_chinabond_curve(
            start,
            end,
            force_refresh=force_refresh,
        )
    elif source == "akshare":
        curve = fetch_china_yield_curve(start, end)
    else:
        raise ValueError(f"Unsupported pipeline source: {source}")
    return MarketDataset(
        curve=curve,
        issuance=sample.issuance.iloc[0:0].copy(),
        news=sample.news.iloc[0:0].copy(),
    )


def _artifact_metadata(path: Path, relative_to: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(relative_to).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def run_pipeline(
    *,
    source: str,
    start: str | None = None,
    end: str | None = None,
    destination: Path | None = None,
    force_refresh: bool = False,
    started_at: datetime | None = None,
) -> PipelineResult:
    """Run a validated report pipeline and atomically publish its artifacts."""
    if source not in PIPELINE_SOURCES:
        raise ValueError(f"Unsupported pipeline source: {source}")
    if source != "demo" and (not start or not end):
        raise ValueError("start and end are required for official and akshare sources")

    started = started_at or datetime.now(timezone.utc)
    if started.tzinfo is None:
        raise ValueError("started_at must include timezone information")
    started = started.astimezone(timezone.utc)
    run_id = f"{started:%Y%m%dT%H%M%SZ}-{source}"
    root = Path(destination) if destination is not None else output_dir() / "runs"
    final_dir = root / run_id
    if final_dir.exists():
        raise FileExistsError(f"Pipeline run already exists: {final_dir}")

    dataset = _load_dataset(source, start, end, force_refresh)
    root.mkdir(parents=True, exist_ok=True)
    staging = root / f".{run_id}.{uuid4().hex[:8]}.tmp"
    staging.mkdir()
    try:
        normalized_curve, quality = validate_market_dataset(
            dataset.curve,
            dataset.issuance,
            dataset.news,
            expected_source=source,
        )
        curve_path = staging / "normalized_yield_curve.csv"
        normalized_curve.to_csv(curve_path, index=False, date_format="%Y-%m-%d")

        quality_path = staging / "data_quality.json"
        quality_path.write_text(
            json.dumps(quality, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        markdown_path, workbook_path = write_report_bundle(
            normalized_curve,
            dataset.issuance,
            dataset.news,
            destination=staging,
        )
        artifacts = [
            _artifact_metadata(path, staging)
            for path in (curve_path, quality_path, markdown_path, workbook_path)
        ]
        manifest = {
            "status": "succeeded",
            "run_id": run_id,
            "source": source,
            "start": start,
            "end": end,
            "force_refresh": force_refresh,
            "started_at_utc": started.isoformat(),
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "package_version": __version__,
            "artifacts": artifacts,
        }
        manifest_path = staging / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        staging.replace(final_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    return PipelineResult(
        run_dir=final_dir,
        quality_path=final_dir / quality_path.name,
        manifest_path=final_dir / manifest_path.name,
    )
