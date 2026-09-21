from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .paths import PROJECT_ROOT


TENOR_TO_YEARS = {
    "3月": 0.25,
    "6月": 0.5,
    "1年": 1.0,
    "2年": 2.0,
    "3年": 3.0,
    "5年": 5.0,
    "7年": 7.0,
    "10年": 10.0,
    "30年": 30.0,
}


class DataSourceError(RuntimeError):
    """Raised when an upstream market-data source cannot be normalized."""


@dataclass(frozen=True)
class MarketDataset:
    curve: pd.DataFrame
    issuance: pd.DataFrame
    news: pd.DataFrame


def sample_dataset(data_dir: Path | None = None) -> MarketDataset:
    base = data_dir or PROJECT_ROOT / "data"
    return MarketDataset(
        curve=pd.read_csv(base / "sample_yield_curve.csv"),
        issuance=pd.read_csv(base / "sample_issuance.csv"),
        news=pd.read_csv(base / "sample_news.csv"),
    )


def fetch_china_yield_curve(
    start_date: str,
    end_date: str,
    curve_keyword: str = "国债收益率曲线",
) -> pd.DataFrame:
    """Fetch a ChinaBond yield curve through AKShare and retain one curve family."""
    try:
        import akshare as ak
    except ImportError as exc:
        raise DataSourceError("AKShare is not installed. Run pip install -e '.[dev]'.") from exc

    try:
        frame = ak.bond_china_yield(start_date=start_date, end_date=end_date)
    except Exception as exc:  # Network and upstream errors need contextual wrapping.
        raise DataSourceError(f"AKShare yield-curve request failed: {exc}") from exc

    if frame.empty:
        raise DataSourceError("AKShare returned no yield-curve rows")

    curve_column = next(
        (name for name in ("曲线名称", "curve_name") if name in frame.columns),
        None,
    )
    if curve_column is None:
        raise DataSourceError(f"Curve-name column missing. Received: {list(frame.columns)}")

    matches = frame[curve_column].astype(str).str.contains(curve_keyword, na=False)
    selected = frame.loc[matches].copy()
    if selected.empty:
        available = frame[curve_column].dropna().astype(str).unique()[:10]
        raise DataSourceError(
            f"No curve matched {curve_keyword!r}. Available examples: {available.tolist()}"
        )

    selected = selected.rename(columns={curve_column: "curve_name", "日期": "date"})
    selected["source"] = "AKShare/ChinaBond"
    tenor_columns = [column for column in TENOR_TO_YEARS if column in selected.columns]
    if len(tenor_columns) < 4:
        raise DataSourceError(
            f"Too few supported tenor columns. Received: {list(selected.columns)}"
        )
    expected = ["curve_name", "date", *tenor_columns, "source"]
    return selected[expected].sort_values("date").reset_index(drop=True)
