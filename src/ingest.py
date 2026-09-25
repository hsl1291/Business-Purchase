"""Normalize a raw state license / SOS export into a common schema.

Different states and license boards export wildly different column names.
This module reads `config/scoring.yaml`'s `field_map` to translate whatever
raw CSV you have into one consistent schema that score.py, estimate.py, and
downstream tooling can all rely on.

Usage:
    python -m src.ingest data/raw/state_licenses.csv --config config/scoring.yaml -o data/normalized.csv
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd
import yaml

# The canonical schema every downstream module expects. Optional fields may
# be blank/NaN if the raw source doesn't provide them.
CANONICAL_FIELDS = [
    "business_name",
    "license_number",
    "license_type",
    "license_status",
    "issue_date",
    "renewal_date",
    "principal_name",
    "address",
    "city",
    "state",
    "zip",
    "naics_code",
    "employee_count",
]

REQUIRED_FIELDS = ["business_name", "license_status", "issue_date"]


def load_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def normalize(raw_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    field_map = config["field_map"]
    date_format = config.get("date_format", "%m/%d/%Y")

    out = pd.DataFrame()
    missing_required = []

    for canonical, source_col in field_map.items():
        if canonical not in CANONICAL_FIELDS:
            continue
        if not source_col:
            out[canonical] = pd.NA
            continue
        if source_col not in raw_df.columns:
            if canonical in REQUIRED_FIELDS:
                missing_required.append((canonical, source_col))
            out[canonical] = pd.NA
            continue
        out[canonical] = raw_df[source_col]

    if missing_required:
        details = ", ".join(f"{c} (expected column '{s}')" for c, s in missing_required)
        raise ValueError(
            f"Required field(s) not found in raw CSV: {details}. "
            f"Check config['field_map'] against your raw file's actual headers."
        )

    # Fill in any canonical fields the field_map didn't mention at all.
    for canonical in CANONICAL_FIELDS:
        if canonical not in out.columns:
            out[canonical] = pd.NA

    # Parse dates; leave unparseable values as NaT rather than raising, since
    # partial/dirty government data is the norm, not the exception.
    for date_col in ("issue_date", "renewal_date"):
        out[date_col] = pd.to_datetime(out[date_col], format=date_format, errors="coerce")

    out["employee_count"] = pd.to_numeric(out["employee_count"], errors="coerce")

    return out[CANONICAL_FIELDS]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_csv", help="Path to the raw license/SOS export CSV")
    parser.add_argument("--config", required=True, help="Path to config/scoring.yaml")
    parser.add_argument("-o", "--output", required=True, help="Path to write the normalized CSV")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    raw_df = pd.read_csv(args.raw_csv, dtype=str)
    normalized = normalize(raw_df, config)
    normalized.to_csv(args.output, index=False)

    n_dropped_status = normalized["license_status"].isna().sum()
    print(f"Wrote {len(normalized)} rows to {args.output}")
    if n_dropped_status:
        print(f"Warning: {n_dropped_status} rows have no license_status value.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
