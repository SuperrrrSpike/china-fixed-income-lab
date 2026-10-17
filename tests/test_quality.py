from __future__ import annotations

import json

import pandas as pd
import pytest

from fixed_income_lab.data import sample_dataset
from fixed_income_lab.quality import DataQualityError, validate_market_dataset
from fixed_income_lab.yield_curve import to_long_curve


def test_validate_demo_dataset_returns_serializable_summary():
    dataset = sample_dataset()

    normalized, summary = validate_market_dataset(
        dataset.curve,
        dataset.issuance,
        dataset.news,
        expected_source="demo",
    )

    assert len(normalized) == len(to_long_curve(dataset.curve))
    assert summary["status"] == "passed"
    assert summary["curve"]["row_count"] == len(normalized)
    assert summary["curve"]["date_count"] >= 2
    assert summary["curve"]["tenor_count"] >= 4
    assert summary["curve"]["data_statuses"] == ["synthetic_sample"]
    json.dumps(summary)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda frame: frame.drop(columns=["curve_name"]), "identifiers"),
        (
            lambda frame: pd.concat([frame, frame.iloc[[0]]], ignore_index=True),
            "duplicate",
        ),
        (lambda frame: frame.assign(yield_pct=99.0), "yield"),
        (lambda frame: frame.assign(tenor_years=101.0), "tenor"),
    ],
)
def test_validate_curve_rejects_invalid_data(mutation, message):
    dataset = sample_dataset()
    curve = to_long_curve(dataset.curve)

    with pytest.raises(DataQualityError, match=message):
        validate_market_dataset(
            mutation(curve),
            dataset.issuance,
            dataset.news,
            expected_source="demo",
        )


def test_validate_official_data_requires_provenance_fields():
    dataset = sample_dataset()
    curve = to_long_curve(dataset.curve).assign(
        source="ChinaBond/CCDC official annual file",
        data_status="official_primary",
    )

    with pytest.raises(DataQualityError, match="provenance"):
        validate_market_dataset(
            curve,
            dataset.issuance.iloc[0:0].copy(),
            dataset.news.iloc[0:0].copy(),
            expected_source="official",
        )


def test_validate_curve_rejects_unparseable_observations():
    dataset = sample_dataset()
    curve = to_long_curve(dataset.curve)
    curve["yield_pct"] = curve["yield_pct"].astype(object)
    curve.loc[0, "yield_pct"] = "not-a-number"

    with pytest.raises(DataQualityError, match="unparseable"):
        validate_market_dataset(
            curve,
            dataset.issuance,
            dataset.news,
            expected_source="demo",
        )


def test_validate_official_data_accepts_complete_provenance():
    dataset = sample_dataset()
    curve = to_long_curve(dataset.curve).assign(
        source="ChinaBond/CCDC official annual file",
        source_url="https://example.test/curve.xlsx",
        source_sha256="a" * 64,
        retrieved_at_utc="2026-10-18T00:00:00+00:00",
        data_status="official_primary",
    )

    _, summary = validate_market_dataset(
        curve,
        dataset.issuance.iloc[0:0].copy(),
        dataset.news.iloc[0:0].copy(),
        expected_source="official",
    )

    assert summary["status"] == "passed"
    assert summary["curve"]["data_statuses"] == ["official_primary"]


def test_validate_official_data_accepts_published_zero_tenor():
    dataset = sample_dataset()
    curve = to_long_curve(dataset.curve).assign(
        source="ChinaBond/CCDC official annual file",
        source_url="https://example.test/curve.xlsx",
        source_sha256="a" * 64,
        retrieved_at_utc="2026-10-18T00:00:00+00:00",
        data_status="official_primary",
    )
    curve.loc[0, "tenor_years"] = 0.0

    normalized, _ = validate_market_dataset(
        curve,
        dataset.issuance.iloc[0:0].copy(),
        dataset.news.iloc[0:0].copy(),
        expected_source="official",
    )

    assert 0.0 in normalized["tenor_years"].values
