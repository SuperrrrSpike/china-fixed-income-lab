from __future__ import annotations

import numpy as np
import pandas as pd

from .data import TENOR_TO_YEARS


REQUIRED_LONG_COLUMNS = {"curve_name", "date", "tenor_years", "yield_pct", "source"}


def to_long_curve(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert the AKShare-style wide curve into a validated long table."""
    if REQUIRED_LONG_COLUMNS.issubset(frame.columns):
        result = frame.copy()
    else:
        id_vars = [column for column in ("curve_name", "date", "source") if column in frame]
        missing_ids = {"curve_name", "date"} - set(id_vars)
        if missing_ids:
            raise ValueError(f"Curve identifiers missing: {sorted(missing_ids)}")
        tenor_columns = [column for column in TENOR_TO_YEARS if column in frame.columns]
        if not tenor_columns:
            raise ValueError("No supported tenor columns were found")
        result = frame.melt(
            id_vars=id_vars,
            value_vars=tenor_columns,
            var_name="tenor",
            value_name="yield_pct",
        )
        result["tenor_years"] = result["tenor"].map(TENOR_TO_YEARS)
        if "source" not in result:
            result["source"] = "unknown"

    result["date"] = pd.to_datetime(result["date"])
    result["tenor_years"] = pd.to_numeric(result["tenor_years"], errors="coerce")
    result["yield_pct"] = pd.to_numeric(result["yield_pct"], errors="coerce")
    result = result.dropna(subset=["date", "tenor_years", "yield_pct"])
    if result.empty:
        raise ValueError("Curve contains no valid numeric observations")
    return result.sort_values(["curve_name", "date", "tenor_years"]).reset_index(drop=True)


def with_daily_changes(curve_long: pd.DataFrame) -> pd.DataFrame:
    result = to_long_curve(curve_long)
    result["change_bp"] = (
        result.groupby(["curve_name", "tenor_years"])["yield_pct"].diff() * 100.0
    )
    return result


def latest_curve(curve_long: pd.DataFrame) -> pd.DataFrame:
    result = to_long_curve(curve_long)
    latest_date = result["date"].max()
    return result[result["date"] == latest_date].copy()


def yield_at_tenor(
    curve_long: pd.DataFrame,
    tenor_years: float,
    as_of: pd.Timestamp | str | None = None,
) -> tuple[float, bool]:
    result = to_long_curve(curve_long)
    selected_date = pd.Timestamp(as_of) if as_of is not None else result["date"].max()
    snapshot = result[result["date"] == selected_date].sort_values("tenor_years")
    if snapshot.empty:
        raise ValueError(f"No curve observations found for {selected_date.date()}")
    exact = snapshot[snapshot["tenor_years"] == tenor_years]
    if not exact.empty:
        return float(exact.iloc[0]["yield_pct"]), False
    minimum = float(snapshot["tenor_years"].min())
    maximum = float(snapshot["tenor_years"].max())
    if not minimum <= tenor_years <= maximum:
        raise ValueError(f"Tenor {tenor_years}Y is outside the curve range")
    value = np.interp(
        tenor_years,
        snapshot["tenor_years"].to_numpy(dtype=float),
        snapshot["yield_pct"].to_numpy(dtype=float),
    )
    return float(value), True


def term_spread(curve_long: pd.DataFrame, short_tenor: float, long_tenor: float) -> float:
    short_yield, _ = yield_at_tenor(curve_long, short_tenor)
    long_yield, _ = yield_at_tenor(curve_long, long_tenor)
    return float((long_yield - short_yield) * 100.0)


def interpolate_yield(curve_long: pd.DataFrame, maturity_years: float) -> float:
    value, _ = yield_at_tenor(curve_long, maturity_years)
    return value


def apply_curve_scenario(
    curve_long: pd.DataFrame,
    scenario: str,
    magnitude_bp: float,
) -> pd.DataFrame:
    latest = latest_curve(curve_long)
    tenor = latest["tenor_years"].to_numpy(dtype=float)
    scale = (tenor - tenor.min()) / (tenor.max() - tenor.min())
    if scenario == "parallel":
        shock = np.full_like(tenor, magnitude_bp)
    elif scenario == "steepener":
        shock = (scale - 0.5) * 2.0 * magnitude_bp
    elif scenario == "flattener":
        shock = (0.5 - scale) * 2.0 * magnitude_bp
    else:
        raise ValueError("Scenario must be parallel, steepener, or flattener")
    latest["scenario"] = scenario
    latest["shock_bp"] = shock
    latest["shocked_yield_pct"] = latest["yield_pct"] + shock / 100.0
    return latest
