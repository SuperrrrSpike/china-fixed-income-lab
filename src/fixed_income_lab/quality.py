from __future__ import annotations

from typing import Any

import pandas as pd

from .data import TENOR_TO_YEARS
from .issuance import REQUIRED_COLUMNS as ISSUANCE_REQUIRED_COLUMNS
from .issuance import normalize_issuance
from .yield_curve import REQUIRED_LONG_COLUMNS, to_long_curve


NEWS_REQUIRED_COLUMNS = {"date", "category", "title", "impact", "source"}
OFFICIAL_PROVENANCE_COLUMNS = {
    "source_url",
    "source_sha256",
    "retrieved_at_utc",
    "data_status",
}


class DataQualityError(ValueError):
    """Raised when market data fails a publication quality gate."""


def _nonempty_text(frame: pd.DataFrame, columns: set[str]) -> bool:
    return all(
        frame[column].notna().all() and frame[column].astype(str).str.strip().ne("").all()
        for column in columns
    )


def _validate_curve(
    curve: pd.DataFrame,
    expected_source: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if REQUIRED_LONG_COLUMNS.issubset(curve.columns):
        expected_observations = len(curve)
    else:
        tenor_columns = [column for column in TENOR_TO_YEARS if column in curve.columns]
        expected_observations = int(curve[tenor_columns].notna().sum().sum())
    try:
        normalized = to_long_curve(curve)
    except (KeyError, TypeError, ValueError) as exc:
        raise DataQualityError(f"Curve identifiers or values are invalid: {exc}") from exc

    if len(normalized) != expected_observations:
        raise DataQualityError("Curve contains missing or unparseable observations")

    if normalized.duplicated(["curve_name", "date", "tenor_years"]).any():
        raise DataQualityError("Curve contains duplicate curve-date-tenor observations")
    if not normalized["yield_pct"].between(-5.0, 30.0).all():
        raise DataQualityError("Curve yield values must be between -5% and 30%")
    if not normalized["tenor_years"].between(0.0, 100.0).all():
        raise DataQualityError("Curve tenor values must be between 0 and 100 years")
    if not _nonempty_text(normalized, {"curve_name", "source"}):
        raise DataQualityError("Curve name and source must be non-empty")

    source_text = normalized["source"].astype(str)
    if expected_source == "demo":
        if not source_text.str.contains("synthetic", case=False, na=False).all():
            raise DataQualityError("Demo data must be marked as synthetic")
        normalized["data_status"] = "synthetic_sample"
    elif expected_source == "official":
        missing = OFFICIAL_PROVENANCE_COLUMNS - set(normalized.columns)
        if missing or not _nonempty_text(normalized, OFFICIAL_PROVENANCE_COLUMNS):
            raise DataQualityError(
                "Official curve provenance is incomplete: "
                f"missing or empty {sorted(missing or OFFICIAL_PROVENANCE_COLUMNS)}"
            )
        if not normalized["source_sha256"].astype(str).str.fullmatch(r"[0-9a-f]{64}").all():
            raise DataQualityError("Official curve provenance has an invalid SHA-256")
        retrieved = pd.to_datetime(normalized["retrieved_at_utc"], errors="coerce", utc=True)
        if retrieved.isna().any():
            raise DataQualityError("Official curve provenance has an invalid retrieval time")
        if not normalized["data_status"].eq("official_primary").all():
            raise DataQualityError("Official curve must use data_status=official_primary")
    elif expected_source == "akshare":
        if not source_text.str.contains("AKShare", case=False, na=False).all():
            raise DataQualityError("AKShare mode received data from an unexpected source")
        normalized["data_status"] = "fallback_adapter"
    else:
        raise ValueError(f"Unsupported expected source: {expected_source}")

    statuses = sorted(normalized["data_status"].dropna().astype(str).unique().tolist())
    summary = {
        "row_count": int(len(normalized)),
        "date_count": int(normalized["date"].nunique()),
        "tenor_count": int(normalized["tenor_years"].nunique()),
        "date_min": normalized["date"].min().date().isoformat(),
        "date_max": normalized["date"].max().date().isoformat(),
        "tenors_years": sorted(
            float(value) for value in normalized["tenor_years"].unique().tolist()
        ),
        "sources": sorted(normalized["source"].astype(str).unique().tolist()),
        "data_statuses": statuses,
    }
    return normalized, summary


def _validate_issuance(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    missing = ISSUANCE_REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise DataQualityError(f"Issuance columns missing: {sorted(missing)}")
    try:
        normalized = normalize_issuance(frame)
    except (KeyError, TypeError, ValueError) as exc:
        raise DataQualityError(f"Issuance data is invalid: {exc}") from exc
    if len(normalized) != len(frame):
        raise DataQualityError("Issuance contains invalid dates, names, or bond types")
    if not normalized.empty:
        if normalized["term_years"].isna().any() or not normalized["term_years"].between(
            0.0, 100.0, inclusive="neither"
        ).all():
            raise DataQualityError("Issuance tenor values must be greater than 0 and below 100")
        sizes = normalized["issue_size_billion"].dropna()
        if (sizes < 0).any():
            raise DataQualityError("Issuance size must not be negative")
    return normalized, {"row_count": int(len(normalized))}


def _validate_news(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    missing = NEWS_REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise DataQualityError(f"News columns missing: {sorted(missing)}")
    normalized = frame.copy()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
    if normalized["date"].isna().any():
        raise DataQualityError("News contains invalid dates")
    if not normalized.empty and not _nonempty_text(
        normalized, {"category", "title", "impact", "source"}
    ):
        raise DataQualityError("News text fields must be non-empty")
    return normalized, {"row_count": int(len(normalized))}


def validate_market_dataset(
    curve: pd.DataFrame,
    issuance: pd.DataFrame,
    news: pd.DataFrame,
    *,
    expected_source: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Validate publication inputs and return a normalized curve plus audit summary."""
    normalized_curve, curve_summary = _validate_curve(curve, expected_source)
    _, issuance_summary = _validate_issuance(issuance)
    _, news_summary = _validate_news(news)
    checks = [
        "curve_schema",
        "curve_unique_key",
        "curve_numeric_ranges",
        "source_provenance",
        "issuance_schema_and_values",
        "news_schema_and_values",
    ]
    return normalized_curve, {
        "status": "passed",
        "expected_source": expected_source,
        "check_count": len(checks),
        "checks": [{"name": name, "status": "passed"} for name in checks],
        "curve": curve_summary,
        "issuance": issuance_summary,
        "news": news_summary,
    }
