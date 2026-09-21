from __future__ import annotations

from datetime import date

import pandas as pd


REQUIRED_COLUMNS = {
    "bond_name",
    "bond_type",
    "issue_date",
    "term_years",
    "issue_size_billion",
    "bid_method",
    "status",
    "source",
}


def normalize_issuance(frame: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Issuance columns missing: {sorted(missing)}")
    result = frame.copy()
    result["issue_date"] = pd.to_datetime(result["issue_date"], errors="coerce")
    result["term_years"] = pd.to_numeric(result["term_years"], errors="coerce")
    result["issue_size_billion"] = pd.to_numeric(
        result["issue_size_billion"], errors="coerce"
    )
    if "result_yield_pct" in result:
        result["result_yield_pct"] = pd.to_numeric(
            result["result_yield_pct"], errors="coerce"
        )
    result = result.dropna(subset=["issue_date", "bond_name", "bond_type"])
    return result.sort_values("issue_date").reset_index(drop=True)


def upcoming_issuance(
    frame: pd.DataFrame,
    as_of: date | str | pd.Timestamp,
    days: int = 7,
) -> pd.DataFrame:
    result = normalize_issuance(frame)
    start = pd.Timestamp(as_of).normalize()
    end = start + pd.Timedelta(days=days)
    mask = result["issue_date"].between(start, end)
    return result.loc[mask].copy()


def issuance_summary(frame: pd.DataFrame) -> pd.DataFrame:
    result = normalize_issuance(frame)
    return (
        result.groupby(["bond_type", "status"], dropna=False)
        .agg(
            issue_count=("bond_name", "count"),
            issue_size_billion=("issue_size_billion", "sum"),
        )
        .reset_index()
    )

