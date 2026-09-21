from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite

import pandas as pd
from dateutil.relativedelta import relativedelta
from scipy.optimize import brentq


def _to_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


@dataclass(frozen=True)
class BondSpec:
    settlement_date: date | str
    maturity_date: date | str
    coupon_rate: float
    frequency: int = 2
    face_value: float = 100.0

    def __post_init__(self):
        settlement = _to_date(self.settlement_date)
        maturity = _to_date(self.maturity_date)
        if maturity <= settlement:
            raise ValueError("Maturity date must be after settlement date")
        if self.frequency not in (1, 2, 4):
            raise ValueError("Frequency must be 1, 2, or 4")
        if self.coupon_rate < 0 or self.face_value <= 0:
            raise ValueError("Coupon rate and face value must be non-negative/positive")
        object.__setattr__(self, "settlement_date", settlement)
        object.__setattr__(self, "maturity_date", maturity)


class BondAnalytics:
    """Fixed-rate bond analytics using a consistent ACT/365 approximation."""

    def __init__(self, spec: BondSpec):
        self.spec = spec

    @property
    def coupon_amount(self) -> float:
        return self.spec.face_value * self.spec.coupon_rate / self.spec.frequency

    def coupon_dates(self) -> list[date]:
        step_months = 12 // self.spec.frequency
        dates = []
        current = self.spec.maturity_date
        while current > self.spec.settlement_date:
            dates.append(current)
            current -= relativedelta(months=step_months)
        return sorted(dates)

    def previous_and_next_coupon(self) -> tuple[date, date]:
        next_coupon = self.coupon_dates()[0]
        previous = next_coupon - relativedelta(months=12 // self.spec.frequency)
        return previous, next_coupon

    def accrued_interest(self) -> float:
        previous, following = self.previous_and_next_coupon()
        elapsed = (self.spec.settlement_date - previous).days
        period_days = (following - previous).days
        fraction = max(0.0, min(1.0, elapsed / period_days))
        return self.coupon_amount * fraction

    def cash_flows(self) -> pd.DataFrame:
        rows = []
        for payment_date in self.coupon_dates():
            amount = self.coupon_amount
            if payment_date == self.spec.maturity_date:
                amount += self.spec.face_value
            rows.append(
                {
                    "payment_date": payment_date,
                    "years": (payment_date - self.spec.settlement_date).days / 365.0,
                    "cash_flow": amount,
                }
            )
        return pd.DataFrame(rows)

    def dirty_price(self, yield_rate: float) -> float:
        if yield_rate <= -self.spec.frequency:
            raise ValueError("Yield is outside the valid compounding range")
        flows = self.cash_flows()
        periods = flows["years"] * self.spec.frequency
        discount = (1.0 + yield_rate / self.spec.frequency) ** periods
        price = float((flows["cash_flow"] / discount).sum())
        if not isfinite(price):
            raise ValueError("Price calculation produced a non-finite value")
        return price

    def clean_price(self, yield_rate: float) -> float:
        return self.dirty_price(yield_rate) - self.accrued_interest()

    def yield_to_maturity(self, clean_price: float) -> float:
        if clean_price <= 0:
            raise ValueError("Clean price must be positive")

        def objective(rate: float) -> float:
            return self.clean_price(rate) - clean_price

        return float(brentq(objective, -0.95, 2.0, xtol=1e-12, maxiter=300))

    def risk_metrics(self, yield_rate: float) -> dict[str, float]:
        flows = self.cash_flows()
        periods = flows["years"] * self.spec.frequency
        base = 1.0 + yield_rate / self.spec.frequency
        pv = flows["cash_flow"] / (base**periods)
        dirty = float(pv.sum())
        macaulay = float((flows["years"] * pv).sum() / dirty)
        modified = macaulay / base
        convexity = float(
            (
                flows["cash_flow"]
                * flows["years"]
                * (flows["years"] + 1.0 / self.spec.frequency)
                / (base ** (periods + 2.0))
            ).sum()
            / dirty
        )
        bump = 0.0001
        price_down = self.clean_price(yield_rate - bump)
        price_up = self.clean_price(yield_rate + bump)
        dv01 = (price_down - price_up) / 2.0
        return {
            "dirty_price": dirty,
            "clean_price": dirty - self.accrued_interest(),
            "accrued_interest": self.accrued_interest(),
            "macaulay_duration": macaulay,
            "modified_duration": modified,
            "convexity": convexity,
            "dv01": dv01,
        }

    def scenario_table(self, yield_rate: float, shocks_bp: list[float]) -> pd.DataFrame:
        base_price = self.clean_price(yield_rate)
        rows = []
        for shock_bp in shocks_bp:
            shocked_yield = yield_rate + shock_bp / 10_000.0
            shocked_price = self.clean_price(shocked_yield)
            rows.append(
                {
                    "shock_bp": shock_bp,
                    "yield_pct": shocked_yield * 100.0,
                    "clean_price": shocked_price,
                    "price_change": shocked_price - base_price,
                    "return_pct": (shocked_price / base_price - 1.0) * 100.0,
                }
            )
        return pd.DataFrame(rows)

