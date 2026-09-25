import pandas as pd

from src.deal_tracker import build_comparison


def make_deal(name, net_profit, owner_comp, asking_price, multiple_low=2.0, multiple_high=3.0):
    return (
        name,
        {
            "pnl": {"net_profit": net_profit, "owner_compensation": owner_comp, "add_backs": {}},
            "deal_assumptions": {
                "multiple_low": multiple_low,
                "multiple_high": multiple_high,
                "down_payment_pct": 0.10,
                "annual_rate": 0.115,
                "term_years": 10,
                "min_dscr": 1.25,
                "asking_price": asking_price,
            },
        },
    )


def test_build_comparison_includes_all_deals():
    deals = [
        make_deal("Strong Deal", 150000, 50000, 300000),
        make_deal("Weak Deal", 40000, 20000, 500000),
    ]
    df = build_comparison(deals)
    assert set(df["deal_name"]) == {"Strong Deal", "Weak Deal"}
    assert "headroom_vs_max_price" in df.columns


def test_build_comparison_sorts_by_headroom_descending():
    deals = [
        make_deal("Weak Deal", 40000, 20000, 500000),   # asking way more than SDE supports
        make_deal("Strong Deal", 150000, 50000, 300000),  # conservative ask
    ]
    df = build_comparison(deals)
    assert df.iloc[0]["deal_name"] == "Strong Deal"
    assert df.iloc[0]["headroom_vs_max_price"] > df.iloc[1]["headroom_vs_max_price"]


def test_build_comparison_flags_failing_dscr():
    deals = [make_deal("Overpriced", 30000, 20000, 600000)]
    df = build_comparison(deals)
    assert df.iloc[0]["passes_dscr"] == False  # noqa: E712


def test_build_comparison_skips_malformed_deal(capsys):
    deals = [
        ("Broken Deal", {"pnl": {}, "deal_assumptions": {}}),  # missing net_profit -> KeyError
        make_deal("Good Deal", 100000, 40000, 250000),
    ]
    df = build_comparison(deals)
    assert list(df["deal_name"]) == ["Good Deal"]
