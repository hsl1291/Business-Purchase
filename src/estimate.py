"""Pre-contact rough valuation range.

This estimates a plausible value range from industry benchmarks and employee
count alone -- no actual financials. It exists to help you prioritize a long
list, NOT to quote a number to anyone. It will be wrong by a wide margin on
any individual business; only trust it in aggregate, across a list.

Formula per row:
    revenue_est   = employee_count * revenue_per_employee (from NAICS benchmark)
    sde_est       = revenue_est * sde_margin (from NAICS benchmark)
    value_low     = sde_est * multiple_low
    value_high    = sde_est * multiple_high

Usage:
    python -m src.estimate data/ranked.csv --benchmarks data/benchmarks.csv -o data/ranked_with_estimate.csv
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd


def load_benchmarks(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def estimate(df: pd.DataFrame, benchmarks: pd.DataFrame) -> pd.DataFrame:
    default_row = benchmarks[benchmarks["naics_code"] == "default"].iloc[0]

    def _lookup(naics_code) -> pd.Series:
        if pd.isna(naics_code):
            return default_row
        match = benchmarks[benchmarks["naics_code"] == str(naics_code)]
        return match.iloc[0] if len(match) else default_row

    out = df.copy()
    revenue_est = []
    sde_est = []
    value_low = []
    value_high = []
    industry = []

    for _, row in out.iterrows():
        bench = _lookup(row.get("naics_code"))
        employees = row.get("employee_count")
        # If employee_count is missing, fall back to a conservative estimate
        # so the row still gets a (wide, clearly-marked) range rather than
        # being silently dropped from the output.
        if pd.isna(employees):
            employees = 10  # rough small-business default

        rev = employees * bench["revenue_per_employee"]
        sde = rev * bench["sde_margin"]
        revenue_est.append(rev)
        sde_est.append(sde)
        value_low.append(sde * bench["multiple_low"])
        value_high.append(sde * bench["multiple_high"])
        industry.append(bench["industry"])

    out["est_industry_benchmark"] = industry
    out["est_revenue"] = revenue_est
    out["est_sde"] = sde_est
    out["est_value_low"] = value_low
    out["est_value_high"] = value_high
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ranked_csv", help="Path to a ranked CSV (from src.score) or any CSV with naics_code/employee_count")
    parser.add_argument("--benchmarks", required=True, help="Path to data/benchmarks.csv")
    parser.add_argument("-o", "--output", required=True, help="Path to write the CSV with estimates added")
    args = parser.parse_args(argv)

    df = pd.read_csv(args.ranked_csv)
    benchmarks = load_benchmarks(args.benchmarks)
    result = estimate(df, benchmarks)
    result.to_csv(args.output, index=False)

    print(f"Estimated {len(result)} rows -> {args.output}")
    print("Reminder: these are rough, industry-average ranges for prioritization only. "
          "Never present them to a seller as a valuation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
