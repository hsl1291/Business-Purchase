"""Turn the ranked list into an outreach sheet.

Takes the top N not-yet-contacted businesses from a ranked CSV and writes a
sheet with a plain-English "why flagged" for each, the rough value range for
YOUR eyes only, and blank tracking columns. Paste results back into the
ranked CSV's `contacted` / `response` columns (the refit tool reads those).

Outreach note: prefer a personal letter or direct visit for a first
touch. Rules on cold calls/texts vary by state and by whether the number is
a business line; check them before dialing at volume.

Usage:
    bizbuy callsheet data/ranked_with_estimate.csv -n 25 -o data/call_sheet.csv
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

import pandas as pd


def why_flagged(row: pd.Series, now: datetime | None = None) -> str:
    now = now or datetime.now()
    reasons = []

    issue = pd.to_datetime(row.get("issue_date"), errors="coerce")
    if pd.notna(issue) and row.get("signal_license_age", 0) >= 0.5:
        reasons.append(f"licensed {int((now - issue).days / 365.25)} yrs")
    if row.get("signal_single_principal", 0) >= 1:
        reasons.append("single listed principal")
    if row.get("signal_renewal_lapse", 0) >= 1:
        reasons.append("renewal date has passed")
    if row.get("signal_stale_web_presence", 0) >= 0.5:
        reasons.append("thin/no web presence")
    if row.get("signal_owns_real_estate", 0) >= 1:
        reasons.append("owner appears to own property")
    return "; ".join(reasons) or "score-only (no single dominant signal)"


def build_sheet(df: pd.DataFrame, n: int, now: datetime | None = None) -> pd.DataFrame:
    df = df.copy()
    if "contacted" in df.columns:
        df = df[df["contacted"].isna() | (df["contacted"].astype(str).str.strip() == "")]
    df = df.sort_values("seller_score", ascending=False).head(n)

    sheet = pd.DataFrame({
        "business_name": df["business_name"],
        "principal_name": df.get("principal_name"),
        "address": df.get("address"),
        "city": df.get("city"),
        "seller_score": df["seller_score"].round(3),
        "why_flagged": df.apply(lambda r: why_flagged(r, now), axis=1),
    })
    if "est_value_low" in df.columns:
        sheet["internal_est_value_range"] = (
            "$" + df["est_value_low"].round(-3).map("{:,.0f}".format)
            + " - $" + df["est_value_high"].round(-3).map("{:,.0f}".format)
        )
    for col in ("contact_date", "channel", "outcome", "notes"):
        sheet[col] = ""
    return sheet.reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ranked_csv")
    parser.add_argument("-n", type=int, default=25, help="How many businesses to include")
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args(argv)

    df = pd.read_csv(args.ranked_csv)
    if "seller_score" not in df.columns:
        print("Error: no seller_score column; run `bizbuy run` first.", file=sys.stderr)
        return 1
    sheet = build_sheet(df, args.n)
    sheet.to_csv(args.output, index=False)
    print(f"Wrote {len(sheet)} rows -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
