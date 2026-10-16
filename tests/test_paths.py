from pathlib import Path

from fixed_income_lab.paths import PROJECT_ROOT, output_dir, raw_data_dir


def test_default_paths_are_local(monkeypatch):
    monkeypatch.delenv("FIXED_INCOME_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("FIXED_INCOME_DATA_DIR", raising=False)

    assert output_dir() == PROJECT_ROOT / "reports"
    assert raw_data_dir() == PROJECT_ROOT / "data" / "raw"


def test_environment_paths_override_local_defaults(monkeypatch, tmp_path: Path):
    report_dir = tmp_path / "reports"
    data_dir = tmp_path / "raw"
    monkeypatch.setenv("FIXED_INCOME_OUTPUT_DIR", str(report_dir))
    monkeypatch.setenv("FIXED_INCOME_DATA_DIR", str(data_dir))

    assert output_dir() == report_dir
    assert raw_data_dir() == data_dir
