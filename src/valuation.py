"""Post-NDA valuation: SDE/EBITDA recast, multiple bands, and SBA loan sizing.

This automates the arithmetic once you have real financials -- it does not
judge whether add-backs are legitimate or whether the numbers reconcile to
tax returns. That's still your (or a QoE reviewer's) job.

Input is a YAML file describing the P&L and proposed deal terms. See
data/sample_pnl.yaml for the expected format.

Usage:
    python -m src.valuation data/sample_pnl.yaml
"""
from __future__ import annotations

import argparse
import sys

import yaml


def compute_sde(pnl: dict) -> float:
    """SDE = net profit + owner compensation + add-backs."""
    net_profit = pnl["net_profit"]
    owner_compensation = pnl.get("owner_compensation", 0)
    add_backs = pnl.get("add_backs", {})
    return net_profit + owner_compensation + sum(add_backs.values())


def compute_ebitda(pnl: dict, market_manager_salary: float) -> float:
    """EBITDA (adjusted) = SDE - a market-rate replacement manager's salary.

    This is the standard way to move from SDE (assumes an owner-operator) to
    an EBITDA figure comparable to lower-middle-market deals, where the buyer
    expects to pay a manager rather than run the business themselves.
    """
    sde = compute_sde(pnl)
    return sde - market_manager_salary


def value_range(earnings: float, multiple_low: float, multiple_high: float) -> tuple[float, float]:
    return earnings * multiple_low, earnings * multiple_high


def sba_loan_payment(loan_amount: float, annual_rate: float, term_years: int) -> float:
    """Standard amortizing loan payment formula, monthly payment * 12."""
    monthly_rate = annual_rate / 12
    n_payments = term_years * 12
    if monthly_rate == 0:
        return loan_amount / term_years
    monthly_payment = (
        loan_amount * monthly_rate * (1 + monthly_rate) ** n_payments
    ) / ((1 + monthly_rate) ** n_payments - 1)
    return monthly_payment * 12


def dscr(available_cash_flow: float, annual_debt_service: float) -> float:
    if annual_debt_service == 0:
        return float("inf")
    return available_cash_flow / annual_debt_service


def max_supportable_price(
    sde: float,
    down_payment_pct: float,
    annual_rate: float,
    term_years: int,
    min_dscr: float,
    owner_draw_reserve: float = 0.0,
) -> float:
    """Solve for the highest total price whose SBA-financed debt service the
    business's cash flow can cover at the required DSCR.

    available_cash_flow = sde - owner_draw_reserve (cash the new owner needs
    to live on / reinvest, held out before debt service is tested)
    loan_amount = price * (1 - down_payment_pct)
    We need: available_cash_flow / annual_debt_service(loan_amount) >= min_dscr
    """
    available_cash_flow = sde - owner_draw_reserve
    if available_cash_flow <= 0:
        return 0.0

    max_annual_debt_service = available_cash_flow / min_dscr

    # Solve backward: given max_annual_debt_service, what loan amount produces
    # that payment? Invert the amortization formula.
    monthly_rate = annual_rate / 12
    n_payments = term_years * 12
    monthly_payment = max_annual_debt_service / 12
    if monthly_rate == 0:
        max_loan = monthly_payment * n_payments
    else:
        max_loan = (
            monthly_payment * ((1 + monthly_rate) ** n_payments - 1)
        ) / (monthly_rate * (1 + monthly_rate) ** n_payments)

    max_price = max_loan / (1 - down_payment_pct)
    return max_price


def evaluate(pnl_config: dict) -> dict:
    pnl = pnl_config["pnl"]
    deal = pnl_config.get("deal_assumptions", {})

    sde = compute_sde(pnl)
    market_manager_salary = deal.get("market_manager_salary", 0)
    ebitda = compute_ebitda(pnl, market_manager_salary) if market_manager_salary else None

    multiple_low = deal.get("multiple_low", 2.0)
    multiple_high = deal.get("multiple_high", 3.0)
    sde_value_low, sde_value_high = value_range(sde, multiple_low, multiple_high)

    down_payment_pct = deal.get("down_payment_pct", 0.10)
    annual_rate = deal.get("annual_rate", 0.115)  # SBA 7(a) variable rate ballpark
    term_years = deal.get("term_years", 10)
    min_dscr = deal.get("min_dscr", 1.25)
    owner_draw_reserve = deal.get("owner_draw_reserve", 0.0)

    max_price = max_supportable_price(
        sde, down_payment_pct, annual_rate, term_years, min_dscr, owner_draw_reserve
    )

    asking_price = deal.get("asking_price")
    result = {
        "sde": sde,
        "ebitda_adjusted": ebitda,
        "sde_multiple_value_range": (sde_value_low, sde_value_high),
        "sba_max_supportable_price": max_price,
        "financing_assumptions": {
            "down_payment_pct": down_payment_pct,
            "annual_rate": annual_rate,
            "term_years": term_years,
            "min_dscr": min_dscr,
        },
    }

    if asking_price is not None:
        loan_amount = asking_price * (1 - down_payment_pct)
        annual_debt_service = sba_loan_payment(loan_amount, annual_rate, term_years)
        available_cash_flow = sde - owner_draw_reserve
        result["asking_price"] = asking_price
        result["asking_price_loan_amount"] = loan_amount
        result["asking_price_annual_debt_service"] = annual_debt_service
        result["asking_price_dscr"] = dscr(available_cash_flow, annual_debt_service)
        result["asking_price_passes_dscr"] = result["asking_price_dscr"] >= min_dscr

    return result


def print_report(result: dict) -> None:
    print("=== Valuation Report ===")
    print(f"SDE (net profit + owner comp + add-backs): ${result['sde']:,.0f}")
    if result["ebitda_adjusted"] is not None:
        print(f"Adjusted EBITDA (SDE - market manager salary): ${result['ebitda_adjusted']:,.0f}")
    lo, hi = result["sde_multiple_value_range"]
    print(f"SDE-multiple value range: ${lo:,.0f} - ${hi:,.0f}")
    print(f"SBA max supportable price (at DSCR >= {result['financing_assumptions']['min_dscr']}): "
          f"${result['sba_max_supportable_price']:,.0f}")

    if "asking_price" in result:
        print()
        print(f"--- Against asking price of ${result['asking_price']:,.0f} ---")
        print(f"Loan amount (after down payment): ${result['asking_price_loan_amount']:,.0f}")
        print(f"Annual debt service: ${result['asking_price_annual_debt_service']:,.0f}")
        print(f"DSCR at asking price: {result['asking_price_dscr']:.2f}")
        verdict = "PASSES" if result["asking_price_passes_dscr"] else "FAILS"
        print(f"-> {verdict} the minimum DSCR test")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pnl_yaml", help="Path to a P&L/deal-assumptions YAML file")
    args = parser.parse_args(argv)

    with open(args.pnl_yaml, "r") as f:
        pnl_config = yaml.safe_load(f)

    result = evaluate(pnl_config)
    print_report(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
