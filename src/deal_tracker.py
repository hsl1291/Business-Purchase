"""Track and compare multiple candidate deals side by side.

Where src.valuation evaluates one P&L YAML at a time, this runs it across a
directory of them and produces one comparison table -- sorted by whichever
column you care about (default: how much cushion the asking price has above
the minimum DSCR).

Usage:
    # Put one YAML per candidate deal in a directory (same format as
    # data/sample_pnl.yaml), then:
    python -m src.deal_tracker data/deals/ -o data/deal_comparison.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

from src.valuation import evaluate


def load_deals(deals_dir: str) -> list[tuple[str, dict]]:
    deals = []
    for path in sorted(Path(deals_dir).glob("*.yaml")):
        with open(path) as f:
            config = yaml.safe_load(f)
        deal_name = config.get("deal_name", path.stem)
        deals.append((deal_name, config))
    if not deals:
        raise ValueError(f"No .yaml files found in {deals_dir}")
    return deals


def build_comparison(deals: list[tuple[str, dict]]) -> pd.DataFrame:
    rows = []
    for name, config in deals:
        try:
            result = evaluate(config)
        except (KeyError, TypeError) as e:
            print(f"Warning: skipping '{name}', malformed deal file: {e}", file=sys.stderr)
            continue

        lo, hi = result["sde_multiple_value_range"]
        row = {
            "deal_name": name,
            "sde": result["sde"],
            "ebitda_adjusted": result["ebitda_adjusted"],
            "value_range_low": lo,
            "value_range_high": hi,
            "sba_max_supportable_price": result["sba_max_supportable_price"],
        }
        if "asking_price" in result:
            row["asking_price"] = result["asking_price"]
            row["asking_price_dscr"] = result["asking_price_dscr"]
            row["passes_dscr"] = result["asking_price_passes_dscr"]
            # positive = room above the price the SBA math would support;
            # negative = asking more than cash flow can finance
            row["headroom_vs_max_price"] = result["sba_max_supportable_price"] - result["asking_price"]
        rows.append(row)

    df = pd.DataFrame(rows)
    if "headroom_vs_max_price" in df.columns:
        df = df.sort_values("headroom_vs_max_price", ascending=False)
    else:
        df = df.sort_values("sba_max_supportable_price", ascending=False)
    return df.reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deals_dir", help="Directory of per-deal P&L YAML files")
    parser.add_argument("-o", "--output", required=True, help="Path to write the comparison CSV")
    args = parser.parse_args(argv)

    deals = load_deals(args.deals_dir)
    comparison = build_comparison(deals)
    comparison.to_csv(args.output, index=False)

    print(f"Compared {len(comparison)} deals -> {args.output}")
    print(comparison.to_string(index=False))
    if "passes_dscr" in comparison.columns and not comparison["passes_dscr"].all():
        n_failing = (~comparison["passes_dscr"]).sum()
        print(f"\n{n_failing} deal(s) fail the minimum DSCR test at their asking price.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
