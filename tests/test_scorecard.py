import math

import pytest

from src.scorecard import band_position, suggested_multiple
from src.valuation import evaluate


def test_no_factors_lands_mid_band():
    multiple, notes = suggested_multiple(2.0, 3.0, {})
    assert math.isclose(multiple, 2.5)
    assert notes == []


def test_risky_business_lands_low_in_band():
    factors = {"owner_dependence": "high", "revenue_trend": "declining", "top_customer_pct": 0.4}
    multiple, _ = suggested_multiple(2.0, 3.0, factors)
    assert multiple == 2.0  # position clipped at 0


def test_strong_business_lands_high_in_band():
    factors = {
        "owner_dependence": "low",
        "revenue_trend": "growing",
        "recurring_revenue": "high",
        "financial_records": "clean",
        "years_in_business": 20,
    }
    multiple, _ = suggested_multiple(2.0, 3.0, factors)
    assert multiple == 3.0  # position clipped at 1


def test_invalid_answer_raises():
    with pytest.raises(ValueError):
        band_position({"owner_dependence": "very high"})


def _deal(sde_net, asking):
    return {
        "pnl": {"net_profit": sde_net, "owner_compensation": 0, "add_backs": {}},
        "deal_assumptions": {"asking_price": asking, "multiple_low": 2.0, "multiple_high": 3.0},
    }


def test_stress_test_dscr_falls_as_sde_shrinks():
    result = evaluate(_deal(200000, 400000))
    values = list(result["stress_test"].values())
    assert values == sorted(values, reverse=True)
    assert math.isclose(result["stress_test"]["0%"], result["asking_price_dscr"])


def test_break_even_haircut_matches_min_dscr():
    result = evaluate(_deal(200000, 600000))
    h = result["break_even_sde_haircut"]
    # At exactly the break-even shortfall, DSCR should equal the minimum.
    stressed = 200000 * (1 - h) / result["asking_price_annual_debt_service"]
    assert math.isclose(stressed, 1.25, rel_tol=1e-6)


def test_evaluate_includes_risk_adjusted_value_when_factors_given():
    config = _deal(200000, 400000)
    config["risk_factors"] = {"owner_dependence": "low"}
    result = evaluate(config)
    assert result["risk_adjusted_multiple"] > 2.5
    assert math.isclose(result["risk_adjusted_value"], 200000 * result["risk_adjusted_multiple"])
