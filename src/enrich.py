"""Populate the enrichment signals that src/score.py otherwise treats as
neutral (0): stale_web_presence and owns_real_estate.

Two different data-availability realities here:

1. stale_web_presence: Google Places API has a real, nationwide, callable
   API. This module calls it for real (requires GOOGLE_PLACES_API_KEY).

2. owns_real_estate: county property/assessor records have no unified
   national API -- every county publishes its own portal, if it publishes
   one at all. This module does NOT call anything for you. Instead it
   documents the manual-join workflow: export owner-name matches from your
   county assessor's site (most let you search/export by owner name) and
   join them in with --assessor-csv. If the county isn't in your assessor
   CSV, the business gets a neutral (0) score for this signal, same as if
   you'd skipped it entirely.

Usage:
    export GOOGLE_PLACES_API_KEY=...
    python -m src.enrich data/ranked.csv -o data/ranked_enriched.csv \
        [--assessor-csv data/assessor_export.csv] [--skip-places]
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import pandas as pd
import requests

PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# A business counts as "stale" if it has no website, OR its Google rating
# count suggests very little recent activity, OR (when available) its last
# review is old. The Places API (New) doesn't return "last review date" in
# the basic tier, so this uses website presence + review count as the two
# signals actually available without a paid tier.
MIN_REVIEW_COUNT_NOT_STALE = 5


def places_lookup(business_name: str, city: str, state: str, api_key: str) -> dict | None:
    """Text-search Google Places for a business and return the fields we
    need. Returns None if not found or on error (caller treats as unknown/
    neutral, never as a penalty -- a missing match isn't evidence of anything).
    """
    query = f"{business_name}, {city}, {state}"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.websiteUri,places.userRatingCount,places.businessStatus",
    }
    try:
        resp = requests.post(
            PLACES_TEXT_SEARCH_URL,
            json={"textQuery": query},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        places = resp.json().get("places", [])
        if not places:
            return None
        return places[0]
    except requests.RequestException as e:
        print(f"  Places lookup failed for '{business_name}': {e}", file=sys.stderr)
        return None


def score_stale_from_place(place: dict | None) -> float:
    if place is None:
        return 0.0  # unknown -> neutral, not penalized
    has_website = bool(place.get("websiteUri"))
    review_count = place.get("userRatingCount", 0) or 0
    is_closed = place.get("businessStatus") not in (None, "OPERATIONAL")

    if is_closed:
        return 1.0  # closed but license still active -> strong signal
    if not has_website and review_count < MIN_REVIEW_COUNT_NOT_STALE:
        return 1.0
    if not has_website or review_count < MIN_REVIEW_COUNT_NOT_STALE:
        return 0.5
    return 0.0


def enrich_web_presence(df: pd.DataFrame, api_key: str, rate_limit_sec: float = 0.1) -> pd.Series:
    scores = []
    for _, row in df.iterrows():
        place = places_lookup(
            str(row.get("business_name", "")),
            str(row.get("city", "")),
            str(row.get("state", "")),
            api_key,
        )
        scores.append(score_stale_from_place(place))
        time.sleep(rate_limit_sec)
    return pd.Series(scores, index=df.index)


def enrich_real_estate(df: pd.DataFrame, assessor_csv: str | None) -> pd.Series:
    """Join against a manually-exported assessor CSV with columns
    `owner_name` and `property_address`. A match on owner_name (case-
    insensitive, whitespace-normalized) between the business's principal
    and a property owner counts as owns_real_estate=1.0.

    This is intentionally simple string matching, not authoritative -- treat
    matches as a hint to verify, not a fact.
    """
    if not assessor_csv:
        return pd.Series(0.0, index=df.index)

    assessor = pd.read_csv(assessor_csv, dtype=str)
    owners = set(
        assessor["owner_name"].dropna().str.strip().str.lower()
    )

    def _matches(principal_name) -> float:
        if pd.isna(principal_name):
            return 0.0
        return 1.0 if str(principal_name).strip().lower() in owners else 0.0

    return df["principal_name"].apply(_matches)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ranked_csv", help="Path to a normalized or ranked CSV (needs business_name, city, state, principal_name)")
    parser.add_argument("-o", "--output", required=True, help="Path to write the enriched CSV")
    parser.add_argument("--assessor-csv", help="Manually-exported county assessor CSV with owner_name column")
    parser.add_argument("--skip-places", action="store_true", help="Skip the Google Places lookup (e.g. no API key yet)")
    args = parser.parse_args(argv)

    df = pd.read_csv(args.ranked_csv)

    if args.skip_places:
        df["stale_web_presence"] = 0.0
        print("Skipped Google Places lookup (--skip-places); stale_web_presence set to neutral 0.")
    else:
        api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
        if not api_key:
            print(
                "GOOGLE_PLACES_API_KEY not set. Set it, or pass --skip-places to "
                "leave stale_web_presence as neutral.",
                file=sys.stderr,
            )
            return 1
        print(f"Looking up {len(df)} businesses in Google Places...")
        df["stale_web_presence"] = enrich_web_presence(df, api_key)

    df["owns_real_estate"] = enrich_real_estate(df, args.assessor_csv)
    if not args.assessor_csv:
        print(
            "No --assessor-csv given; owns_real_estate set to neutral 0 for all rows. "
            "See src/enrich.py docstring for how to get a county export."
        )

    df.to_csv(args.output, index=False)
    print(f"Wrote {len(df)} enriched rows -> {args.output}")
    print(
        "Re-run src.score on this file (it will pick up stale_web_presence / "
        "owns_real_estate columns automatically) to fold enrichment into the ranking."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
