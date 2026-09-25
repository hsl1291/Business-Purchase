"""Seller-likelihood scoring.

This does NOT predict who will sell. It ranks businesses by public signals
that correlate with succession risk and owner disengagement, so you know who
to call first. Treat the output as a prioritized call list, not a list of
sellers -- see README.md for expected response rates.

Usage:
    python -m src.score data/normalized.csv --config config/scoring.yaml -o data/ranked.csv
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

import pandas as pd
import yaml


def load_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def _clip01(series: pd.Series) -> pd.Series:
    return series.clip(lower=0.0, upper=1.0)


def score_license_age(df: pd.DataFrame, config: dict, now: datetime) -> pd.Series:
    max_years = config["license_age"]["max_years"]
    age_years = (now - df["issue_date"]).dt.days / 365.25
    return _clip01(age_years / max_years).fillna(0.0)


def score_single_principal(df: pd.DataFrame) -> pd.Series:
    # Without SOS officer-list data, this is a placeholder that scores 1.0
    # when principal_name is populated and looks like a single person (no
    # "and", "&", or comma-separated second name) and 0.0 otherwise/unknown.
    def _is_single(name) -> float:
        if pd.isna(name) or not str(name).strip():
            return 0.0
        text = str(name).lower()
        if " and " in text or "&" in text or "," in text:
            return 0.0
        return 1.0

    return df["principal_name"].apply(_is_single)


def score_renewal_lapse(df: pd.DataFrame, config: dict, now: datetime) -> pd.Series:
    params = config["renewal_lapse"]
    is_lapsed = df["renewal_date"] < now
    return is_lapsed.map(
        {True: params["lapse_penalty_score"], False: params["on_time_score"]}
    ).fillna(0.0)


def score_stale_web_presence(df: pd.DataFrame) -> pd.Series:
    # Requires enrichment (e.g. Google Places) not performed by this repo.
    # If the column exists and is populated, use it; otherwise neutral (0).
    if "stale_web_presence" in df.columns:
        return pd.to_numeric(df["stale_web_presence"], errors="coerce").fillna(0.0)
    return pd.Series(0.0, index=df.index)


def score_owns_real_estate(df: pd.DataFrame) -> pd.Series:
    # Requires enrichment (e.g. county assessor lookup) not performed by this
    # repo. If the column exists and is populated, use it; otherwise neutral.
    if "owns_real_estate" in df.columns:
        return pd.to_numeric(df["owns_real_estate"], errors="coerce").fillna(0.0)
    return pd.Series(0.0, index=df.index)


def score_size_band_fit(df: pd.DataFrame, config: dict) -> pd.Series:
    params = config["size_band_fit"]
    lo, hi = params["min_employees"], params["max_employees"]
    in_band = (df["employee_count"] >= lo) & (df["employee_count"] <= hi)
    # employee_count missing -> neutral 0, not a penalty
    return in_band.astype(float).where(df["employee_count"].notna(), 0.0)


SIGNAL_FUNCS = {
    "license_age": score_license_age,
    "single_principal": score_single_principal,
    "renewal_lapse": score_renewal_lapse,
    "stale_web_presence": score_stale_web_presence,
    "owns_real_estate": score_owns_real_estate,
    "size_band_fit": score_size_band_fit,
}

# Signals that need `config` and/or `now` beyond just `df`.
_NEEDS_CONFIG = {"license_age", "renewal_lapse", "size_band_fit"}
_NEEDS_NOW = {"license_age", "renewal_lapse"}


def compute_signals(df: pd.DataFrame, config: dict, now: datetime | None = None) -> pd.DataFrame:
    now = now or datetime.now()
    signals = pd.DataFrame(index=df.index)
    for name in config["weights"]:
        func = SIGNAL_FUNCS[name]
        if name in _NEEDS_CONFIG and name in _NEEDS_NOW:
            signals[name] = func(df, config, now)
        elif name in _NEEDS_CONFIG:
            signals[name] = func(df, config)
        else:
            signals[name] = func(df)
    return signals


def apply_filters(df: pd.DataFrame, config: dict, now: datetime | None = None) -> pd.DataFrame:
    now = now or datetime.now()
    filters = config.get("filters", {})
    mask = pd.Series(True, index=df.index)

    include_statuses = filters.get("license_status_include")
    if include_statuses:
        mask &= df["license_status"].isin(include_statuses)

    min_age = filters.get("min_license_age_years")
    if min_age is not None:
        age_years = (now - df["issue_date"]).dt.days / 365.25
        mask &= age_years >= min_age

    excludes = filters.get("exclude_business_name_contains", [])
    if excludes:
        name_lower = df["business_name"].astype(str).str.lower()
        for term in excludes:
            mask &= ~name_lower.str.contains(term.lower(), na=False)

    return df[mask].copy()


def score(df: pd.DataFrame, config: dict, now: datetime | None = None) -> pd.DataFrame:
    filtered = apply_filters(df, config, now)
    signals = compute_signals(filtered, config, now)

    weights = config["weights"]
    total_weight = sum(weights.values())
    weighted = sum(signals[name] * w for name, w in weights.items())
    filtered = filtered.copy()
    filtered["seller_score"] = weighted / total_weight if total_weight else 0.0

    for name in weights:
        filtered[f"signal_{name}"] = signals[name]

    return filtered.sort_values("seller_score", ascending=False).reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("normalized_csv", help="Path to the normalized CSV from src.ingest")
    parser.add_argument("--config", required=True, help="Path to config/scoring.yaml")
    parser.add_argument("-o", "--output", required=True, help="Path to write the ranked CSV")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    df = pd.read_csv(args.normalized_csv, parse_dates=["issue_date", "renewal_date"])
    ranked = score(df, config)
    ranked.to_csv(args.output, index=False)

    print(f"Scored {len(ranked)} businesses (of {len(df)} input rows) -> {args.output}")
    if len(ranked):
        print(f"Top score: {ranked['seller_score'].iloc[0]:.3f}, "
              f"median: {ranked['seller_score'].median():.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
