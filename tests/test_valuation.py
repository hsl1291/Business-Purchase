import math

from src.valuation import (
    compute_sde,
    compute_ebitda,
    value_range,
    sba_loan_payment,
    dscr,
    max_supportable_price,
    evaluate,
)


def test_compute_sde():
    pnl = {
        "net_profit": 95000,
        "owner_compensation": 65000,
        "add_backs": {"depreciation": 18000, "interest": 6000},
    }
    assert compute_sde(pnl) == 95000 + 65000 + 18000 + 6000


def test_compute_ebitda_subtracts_manager_salary():
    pnl = {"net_profit": 100000, "owner_compensation": 50000, "add_backs": {}}
    ebitda = compute_ebitda(pnl, market_manager_salary=60000)
    assert ebitda == 150000 - 60000


def test_value_range_hand_worked_example():
    # $300k SDE at a 2.0-2.5x multiple -> $600k-$750k
    lo, hi = value_range(300000, 2.0, 2.5)
    assert lo == 600000
    assert hi == 750000


def test_sba_loan_payment_known_amortization():
    # $100k loan, 10% annual rate, 10 years -- sanity check against a
    # standard amortization calculator (~$15,858/yr, within rounding).
    annual_payment = sba_loan_payment(100000, 0.10, 10)
    assert math.isclose(annual_payment, 15858, rel_tol=0.01)


def test_dscr_basic():
    assert dscr(125000, 100000) == 1.25
    assert dscr(100000, 0) == float("inf")


def test_max_supportable_price_respects_min_dscr():
    # If SDE covers exactly the debt service on the returned max price at
    # the requested DSCR, the DSCR computed on that price should round-trip.
    sde = 150000
    down_payment_pct = 0.10
    annual_rate = 0.115
    term_years = 10
    min_dscr = 1.25

    max_price = max_supportable_price(sde, down_payment_pct, annual_rate, term_years, min_dscr)
    loan_amount = max_price * (1 - down_payment_pct)
    annual_debt_service = sba_loan_payment(loan_amount, annual_rate, term_years)
    implied_dscr = dscr(sde, annual_debt_service)

    assert math.isclose(implied_dscr, min_dscr, rel_tol=0.01)


def test_max_supportable_price_zero_when_no_cash_flow():
    assert max_supportable_price(0, 0.10, 0.115, 10, 1.25) == 0.0
    assert max_supportable_price(-5000, 0.10, 0.115, 10, 1.25) == 0.0


def test_evaluate_end_to_end_with_asking_price():
    pnl_config = {
        "pnl": {
            "net_profit": 95000,
            "owner_compensation": 65000,
            "add_backs": {
                "depreciation": 18000,
                "interest_on_business_debt": 6000,
                "one_time_repair": 4000,
            },
        },
        "deal_assumptions": {
            "multiple_low": 2.2,
            "multiple_high": 2.8,
            "down_payment_pct": 0.10,
            "annual_rate": 0.115,
            "term_years": 10,
            "min_dscr": 1.25,
            "asking_price": 320000,
        },
    }
    result = evaluate(pnl_config)

    expected_sde = 95000 + 65000 + 18000 + 6000 + 4000
    assert result["sde"] == expected_sde
    assert result["ebitda_adjusted"] is None  # no market_manager_salary set

    lo, hi = result["sde_multiple_value_range"]
    assert math.isclose(lo, expected_sde * 2.2)
    assert math.isclose(hi, expected_sde * 2.8)

    assert result["asking_price"] == 320000
    assert "asking_price_dscr" in result
    assert isinstance(result["asking_price_passes_dscr"], bool)
