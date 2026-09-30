"""Draft a config `field_map` from the headers of any raw license/SOS CSV.

State license boards and Secretary of State exports all name their columns
differently. Rather than hand-editing config/scoring.yaml, point this at
your export: it fuzzy-matches each header to the canonical fields, prints a
ready-to-paste `field_map` block, and lists columns it could not place so
you can decide by hand. It also sniffs the date format.

It suggests; it does not guess silently. Anything ambiguous is flagged.

Usage:
    bizbuy fieldmap data/raw/state_licenses.csv
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime

import pandas as pd

# canonical field -> lowercase keyword patterns, strongest first
PATTERNS: dict[str, list[str]] = {
    "business_name": ["business name", "dba", "company name", "entity name", "licensee name", "trade name", "name of business", "business"],
    "license_number": ["license number", "license no", "license #", "lic num", "lic no", "license id", "permit number"],
    "license_type": ["license type", "lic type", "license class", "classification", "profession", "license category"],
    "license_status": ["license status", "status", "lic status"],
    "issue_date": ["original issue", "orig issue", "issue date", "date issued", "first issued", "initial issue", "effective date", "date licensed"],
    "renewal_date": ["expiration", "expire", "expiry", "renewal date", "exp date"],
    "principal_name": ["owner name", "owner", "principal", "licensee", "registered agent", "officer", "contact name", "qualifier"],
    "address": ["street address", "address 1", "address1", "address", "street", "mailing address"],
    "city": ["city"],
    "state": ["state"],
    "zip": ["zip", "postal"],
    "naics_code": ["naics", "sic"],
    "employee_count": ["employees", "employee count", "number of employees", "headcount", "staff"],
}

DATE_FORMATS = ["%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%d-%b-%Y", "%m-%d-%Y", "%Y/%m/%d", "%B %d, %Y"]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9# ]+", " ", str(text).lower()).strip()


def suggest(columns: list[str]) -> tuple[dict[str, str], dict[str, list[str]], list[str]]:
    """Return (field_map, ambiguous, unmatched_columns)."""
    normed = {c: _norm(c) for c in columns}
    used: set[str] = set()
    field_map: dict[str, str] = {}
    ambiguous: dict[str, list[str]] = {}

    for canonical, keywords in PATTERNS.items():
        for kw in keywords:
            hits = [c for c, n in normed.items() if c not in used and (n == kw or kw in n)]
            if not hits:
                continue
            exact = [c for c in hits if normed[c] == kw]
            chosen = exact or hits
            field_map[canonical] = chosen[0]
            used.add(chosen[0])
            if len(chosen) > 1:
                ambiguous[canonical] = chosen
            break

    return field_map, ambiguous, [c for c in columns if c not in used]


def sniff_date_format(series: pd.Series) -> str | None:
    values = series.dropna().astype(str).head(50)
    if values.empty:
        return None
    best, best_rate = None, 0.0
    for fmt in DATE_FORMATS:
        ok = 0
        for v in values:
            try:
                datetime.strptime(v.strip(), fmt)
                ok += 1
            except ValueError:
                pass
        if ok / len(values) > best_rate:
            best, best_rate = fmt, ok / len(values)
    return best if best_rate >= 0.8 else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_csv")
    args = parser.parse_args(argv)

    df = pd.read_csv(args.raw_csv, dtype=str, nrows=200)
    field_map, ambiguous, unmatched = suggest(list(df.columns))

    print("# Paste into config/scoring.yaml\nfield_map:")
    for canonical in PATTERNS:
        print(f'  {canonical}: "{field_map.get(canonical, "")}"')

    fmt = None
    for col in (field_map.get("issue_date"), field_map.get("renewal_date")):
        if col:
            fmt = sniff_date_format(df[col])
            if fmt:
                break
    print(f'\ndate_format: "{fmt or "%m/%d/%Y"}"' + ("" if fmt else "   # could not detect; check by hand"))

    missing_required = [f for f in ("business_name", "license_status", "issue_date") if f not in field_map]
    if missing_required:
        print(f"\nWARNING: no column matched required field(s): {', '.join(missing_required)}. "
              f"ingest will fail until you map them.", file=sys.stderr)
    for canonical, cols in ambiguous.items():
        print(f"NOTE: {canonical} matched several columns {cols}; picked '{field_map[canonical]}'. Verify.", file=sys.stderr)
    if unmatched:
        print(f"\nUnmatched columns (ignored): {unmatched}", file=sys.stderr)
    return 1 if missing_required else 0


if __name__ == "__main__":
    sys.exit(main())
