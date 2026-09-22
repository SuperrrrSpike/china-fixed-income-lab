from pathlib import Path

from openpyxl import Workbook
import pandas as pd
import pytest

from fixed_income_lab.data import (
    CHINABOND_SOURCE,
    DataSourceError,
    fetch_official_chinabond_curve,
    parse_official_chinabond_workbook,
)


def _write_official_fixture(path: Path, duplicate: bool = False) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(
        ["Date", "Instructions for Standard Terms", "Standard Terms(Yrs)", "Yield(%)"]
    )
    worksheet.append(["2026/09/20", "1y", 1.0, "1.20"])
    worksheet.append(["2026/09/20", "10y", 10.0, "1.68"])
    worksheet.append(["2026/09/21", "1y", 1.0, "1.21"])
    worksheet.append(["2026/09/21", "10y", 10.0, "1.69"])
    if duplicate:
        worksheet.append(["2026/09/21", "10y", 10.0, "1.69"])
    workbook.save(path)


def test_parse_official_chinabond_workbook_adds_provenance(tmp_path: Path):
    workbook_path = tmp_path / "official.xlsx"
    _write_official_fixture(workbook_path)
    result = parse_official_chinabond_workbook(workbook_path, "https://example.test")

    assert len(result) == 4
    assert result["source"].eq(CHINABOND_SOURCE).all()
    assert result["data_status"].eq("official_primary").all()
    assert result["source_url"].eq("https://example.test").all()
    assert result["source_sha256"].str.fullmatch(r"[0-9a-f]{64}").all()
    assert pd.api.types.is_datetime64_any_dtype(result["date"])


def test_official_fetch_uses_cached_annual_file_and_filters_dates(tmp_path: Path):
    workbook_path = tmp_path / "chinabond_government_yield_curve_2026.xlsx"
    _write_official_fixture(workbook_path)
    result = fetch_official_chinabond_curve(
        "20260921",
        "20260921",
        cache_dir=tmp_path,
    )

    assert result["date"].dt.strftime("%Y-%m-%d").unique().tolist() == ["2026-09-21"]
    assert result["tenor_years"].tolist() == [1.0, 10.0]


def test_official_parser_rejects_duplicate_observations(tmp_path: Path):
    workbook_path = tmp_path / "duplicate.xlsx"
    _write_official_fixture(workbook_path, duplicate=True)
    with pytest.raises(DataSourceError, match="duplicate"):
        parse_official_chinabond_workbook(workbook_path, "https://example.test")


def test_official_fetch_rejects_empty_date_range(tmp_path: Path):
    workbook_path = tmp_path / "chinabond_government_yield_curve_2026.xlsx"
    _write_official_fixture(workbook_path)
    with pytest.raises(DataSourceError, match="no rows"):
        fetch_official_chinabond_curve(
            "20260101",
            "20260102",
            cache_dir=tmp_path,
        )
