from pathlib import Path

import pandas as pd

from fixed_income_lab.data import sample_dataset
from fixed_income_lab.issuance import upcoming_issuance
from fixed_income_lab.report import excel_bytes, generate_morning_brief, write_report_bundle


def test_upcoming_issuance_filters_dates():
    dataset = sample_dataset()
    result = upcoming_issuance(dataset.issuance, "2026-09-22", days=3)
    assert len(result) == 3
    assert result["issue_date"].min() == pd.Timestamp("2026-09-23")


def test_brief_contains_key_sections():
    dataset = sample_dataset()
    brief = generate_morning_brief(dataset.curve, dataset.issuance, dataset.news)
    assert "收益率曲线" in brief
    assert "未来七日一级发行" in brief
    assert "2Y-10Y" in brief
    assert "复核清单" in brief


def test_excel_export_is_xlsx():
    dataset = sample_dataset()
    content = excel_bytes(dataset.curve, dataset.issuance, dataset.news)
    assert content[:2] == b"PK"


def test_report_bundle_writes_files(tmp_path: Path):
    dataset = sample_dataset()
    markdown, workbook = write_report_bundle(
        dataset.curve, dataset.issuance, dataset.news, destination=tmp_path
    )
    assert markdown.exists()
    assert workbook.exists()
    assert "债券市场晨报" in markdown.read_text(encoding="utf-8")

