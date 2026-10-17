from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fixed_income_lab import cli
from fixed_income_lab.data import DataSourceError
from fixed_income_lab.pipeline import run_pipeline
from fixed_income_lab.quality import DataQualityError


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_demo_pipeline_publishes_audited_run(tmp_path: Path):
    result = run_pipeline(
        source="demo",
        destination=tmp_path,
        started_at=datetime(2026, 10, 18, 1, 2, 3, tzinfo=timezone.utc),
    )

    assert result.run_dir.name == "20261018T010203Z-demo"
    assert result.run_dir.is_dir()
    expected = {
        "normalized_yield_curve.csv",
        "data_quality.json",
        "manifest.json",
        "fixed_income_brief_20260921.md",
        "fixed_income_brief_20260921.xlsx",
    }
    assert {path.name for path in result.run_dir.iterdir()} == expected

    quality = json.loads(result.quality_path.read_text(encoding="utf-8"))
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert quality["status"] == "passed"
    assert manifest["status"] == "succeeded"
    assert manifest["source"] == "demo"
    assert manifest["run_id"] == result.run_dir.name
    assert "synthetic_sample" in quality["curve"]["data_statuses"]

    for item in manifest["artifacts"]:
        artifact = result.run_dir / item["path"]
        assert artifact.exists()
        assert item["sha256"] == _sha256(artifact)
        assert item["size_bytes"] == artifact.stat().st_size


def test_pipeline_rejects_missing_dates_for_network_sources(tmp_path: Path):
    with pytest.raises(ValueError, match="start and end"):
        run_pipeline(source="official", destination=tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_pipeline_cleans_staging_directory_on_quality_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def fail_validation(*args, **kwargs):
        raise DataQualityError("forced failure")

    monkeypatch.setattr("fixed_income_lab.pipeline.validate_market_dataset", fail_validation)

    with pytest.raises(DataQualityError, match="forced failure"):
        run_pipeline(
            source="demo",
            destination=tmp_path,
            started_at=datetime(2026, 10, 18, 1, 2, 3, tzinfo=timezone.utc),
        )

    assert list(tmp_path.iterdir()) == []


def test_pipeline_refuses_to_overwrite_existing_run(tmp_path: Path):
    started_at = datetime(2026, 10, 18, 1, 2, 3, tzinfo=timezone.utc)
    run_pipeline(source="demo", destination=tmp_path, started_at=started_at)

    with pytest.raises(FileExistsError, match="already exists"):
        run_pipeline(source="demo", destination=tmp_path, started_at=started_at)


def test_pipeline_cli_runs_demo(tmp_path: Path):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "fixed_income_lab.cli",
            "pipeline",
            "--source",
            "demo",
            "--output",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    run_dir = Path(completed.stdout.strip())
    assert run_dir.parent == tmp_path
    assert (run_dir / "manifest.json").exists()


def test_pipeline_cli_reports_missing_network_dates(tmp_path: Path):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "fixed_income_lab.cli",
            "pipeline",
            "--source",
            "official",
            "--output",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "--start and --end are required" in completed.stderr
    assert list(tmp_path.iterdir()) == []


def test_pipeline_cli_reports_source_failure_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    def fail_pipeline(**kwargs):
        raise DataSourceError("source unavailable")

    monkeypatch.setattr(cli, "run_pipeline", fail_pipeline)

    exit_code = cli.main(
        [
            "pipeline",
            "--source",
            "official",
            "--start",
            "20261001",
            "--end",
            "20261017",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.err.strip() == "error: source unavailable"
    assert "Traceback" not in captured.err
