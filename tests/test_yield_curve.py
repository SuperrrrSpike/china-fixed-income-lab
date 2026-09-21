import pandas as pd
import pytest

from fixed_income_lab.data import sample_dataset
from fixed_income_lab.yield_curve import (
    apply_curve_scenario,
    latest_curve,
    term_spread,
    to_long_curve,
    with_daily_changes,
    yield_at_tenor,
)


@pytest.fixture
def curve():
    return sample_dataset().curve


def test_curve_converts_to_long_form(curve):
    result = to_long_curve(curve)
    assert {"date", "tenor_years", "yield_pct"}.issubset(result.columns)
    assert result["tenor_years"].nunique() == 9


def test_latest_curve_has_one_date(curve):
    result = latest_curve(curve)
    assert result["date"].nunique() == 1


def test_term_spread_uses_basis_points(curve):
    assert term_spread(curve, 2.0, 10.0) == pytest.approx(37.0)


def test_missing_two_year_tenor_is_interpolated(curve):
    frame = curve.drop(columns=["2年"])
    value, interpolated = yield_at_tenor(frame, 2.0)
    assert interpolated is True
    assert value == pytest.approx((1.46 + 1.63) / 2)


def test_daily_change_is_in_basis_points(curve):
    result = with_daily_changes(curve)
    ten_year = result[result["tenor_years"] == 10.0].dropna(subset=["change_bp"])
    assert ten_year.iloc[-1]["change_bp"] == pytest.approx(-1.0)


def test_parallel_scenario_is_constant(curve):
    result = apply_curve_scenario(curve, "parallel", 10)
    assert result["shock_bp"].nunique() == 1
    assert result["shock_bp"].iloc[0] == 10


def test_steepener_has_opposite_end_shocks(curve):
    result = apply_curve_scenario(curve, "steepener", 20)
    assert result.iloc[0]["shock_bp"] < 0
    assert result.iloc[-1]["shock_bp"] > 0


def test_missing_tenors_rejected():
    frame = pd.DataFrame({"curve_name": ["x"], "date": ["2026-01-01"]})
    with pytest.raises(ValueError):
        to_long_curve(frame)
