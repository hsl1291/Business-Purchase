"""Risk scorecard: pick where a business sits inside its multiple band.

Industry multiple bands (e.g. 2.0-3.0x SDE) are wide. Where a specific
business lands depends on risk factors a buyer -- and a lender -- will care
about. This makes that judgment explicit and repeatable instead of a gut
feel: each factor nudges a 0-1 "band position" up or down from a neutral
0.5, and the suggested multiple is interpolated between multiple_low and
multiple_high.

The inputs are YOUR assessment from diligence (owner dependence, customer
concentration, trend); nothing here can observe them. The adjustments are
starting conventions, not market-derived -- tune ADJUSTMENTS to your own
deal experience.
"""
from __future__ import annotations

# Each factor maps an answer to a band-position adjustment (added to 0.5).
# Positive = supports a higher multiple, negative = a lower one.
ADJUSTMENTS: dict[str, dict[str, float]] = {
    # How much revenue walks out the door if the owner leaves
    "owner_dependence": {"low": 0.15, "medium": 0.0, "high": -0.20},
    # Revenue trend over the last 3 years
    "revenue_trend": {"growing": 0.15, "flat": 0.0, "declining": -0.25},
    # Recurring / contracted revenue
    "recurring_revenue": {"high": 0.15, "medium": 0.05, "low": 0.0},
    # Books quality: reconciles to tax returns, clean add-backs
    "financial_records": {"clean": 0.10, "adequate": 0.0, "messy": -0.20},
}


def customer_concentration_adjustment(top_customer_pct: float) -> float:
    """Top customer's share of revenue (0-1)."""
    if top_customer_pct >= 0.30:
        return -0.25
    if top_customer_pct >= 0.15:
        return -0.10
    return 0.05


def years_in_business_adjustment(years: float) -> float:
    if years >= 15:
        return 0.10
    if years >= 5:
        return 0.0
    return -0.15


def band_position(factors: dict) -> tuple[float, list[str]]:
    """Return (position in [0, 1], human-readable notes on what moved it)."""
    position = 0.5
    notes: list[str] = []

    for name, table in ADJUSTMENTS.items():
        answer = factors.get(name)
        if answer is None:
            continue
        if answer not in table:
            raise ValueError(
                f"risk_factors.{name} = {answer!r}; expected one of {sorted(table)}"
            )
        adj = table[answer]
        position += adj
        if adj:
            notes.append(f"{name}={answer} ({adj:+.2f})")

    if "top_customer_pct" in factors:
        adj = customer_concentration_adjustment(float(factors["top_customer_pct"]))
        position += adj
        notes.append(f"top_customer_pct={factors['top_customer_pct']} ({adj:+.2f})")

    if "years_in_business" in factors:
        adj = years_in_business_adjustment(float(factors["years_in_business"]))
        position += adj
        if adj:
            notes.append(f"years_in_business={factors['years_in_business']} ({adj:+.2f})")

    return min(1.0, max(0.0, position)), notes


def suggested_multiple(
    multiple_low: float, multiple_high: float, factors: dict
) -> tuple[float, list[str]]:
    position, notes = band_position(factors)
    return multiple_low + position * (multiple_high - multiple_low), notes
