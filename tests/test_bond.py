from datetime import date

import pytest

from fixed_income_lab.bond import BondAnalytics, BondSpec


@pytest.fixture
def bond():
    return BondAnalytics(BondSpec(date(2026, 9, 22), date(2031, 9, 22), 0.022, 2))


def test_higher_yield_reduces_price(bond):
    assert bond.clean_price(0.03) < bond.clean_price(0.02)


def test_clean_plus_accrued_equals_dirty(bond):
    rate = 0.019
    assert bond.clean_price(rate) + bond.accrued_interest() == pytest.approx(
        bond.dirty_price(rate)
    )


def test_yield_round_trip(bond):
    rate = 0.019
    assert bond.yield_to_maturity(bond.clean_price(rate)) == pytest.approx(rate, abs=1e-9)


def test_risk_metrics_are_positive(bond):
    metrics = bond.risk_metrics(0.019)
    assert metrics["macaulay_duration"] > 0
    assert metrics["modified_duration"] > 0
    assert metrics["convexity"] > 0
    assert metrics["dv01"] > 0


def test_scenario_direction(bond):
    scenarios = bond.scenario_table(0.019, [-10, 0, 10]).set_index("shock_bp")
    assert scenarios.loc[-10, "price_change"] > 0
    assert scenarios.loc[10, "price_change"] < 0


def test_invalid_dates_rejected():
    with pytest.raises(ValueError):
        BondSpec("2030-01-01", "2029-01-01", 0.02)

