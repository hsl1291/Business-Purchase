"""Refit signal weights from logged outreach results.

The weights in config/scoring.yaml start as guesses. Once you've contacted
enough businesses and logged outcomes in the 'response' column of your
ranked CSV (see run.py), this fits a logistic regression of response
(1 = positive/interested, 0 = no/negative) on the signal_* columns and
prints suggested new weights.

This does NOT edit config/scoring.yaml for you -- review the suggested
weights against your judgment before updating the config by hand. With a
small sample (under ~50-100 labeled rows), treat this as a sanity check on
your intuition, not as ground truth; logistic regression coefficients are
noisy at that scale.

Usage:
    # In your ranked CSV, fill in 'response' with 1 (positive reply) or
    # 0 (no response / not interested) for every row you've contacted.
    # Leave 'response' blank for rows you haven't contacted yet.
    python tools/refit_weights.py data/ranked_with_estimate.csv
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

try:
    from sklearn.linear_model import LogisticRegression
except ImportError:
    LogisticRegression = None


def load_labeled_rows(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if "response" not in df.columns:
        raise ValueError(
            "No 'response' column found. Add one with 1 (positive reply) or "
            "0 (no/negative) for rows you've contacted; leave blank otherwise."
        )
    labeled = df[df["response"].notna()].copy()
    labeled["response"] = pd.to_numeric(labeled["response"], errors="coerce")
    labeled = labeled[labeled["response"].isin([0, 1])]
    return labeled


def refit(labeled: pd.DataFrame) -> dict[str, float]:
    if LogisticRegression is None:
        raise ImportError("scikit-learn is required for refitting. Install with: pip install scikit-learn")

    signal_cols = [c for c in labeled.columns if c.startswith("signal_")]
    if not signal_cols:
        raise ValueError("No signal_* columns found -- run src.score first so signals are present.")

    X = labeled[signal_cols].fillna(0.0)
    y = labeled["response"]

    if y.nunique() < 2:
        raise ValueError(
            f"Need both positive and negative outcomes logged to fit weights "
            f"(got only {y.unique().tolist()}). Log more outreach results first."
        )

    model = LogisticRegression(max_iter=1000)
    model.fit(X, y)

    # Convert coefficients to positive relative weights (same convention as
    # config/scoring.yaml: larger = more important, all positive, summing to
    # roughly comparable magnitude). Negative coefficients mean the signal
    # is currently working backwards -- flagged, not silently flipped.
    coefs = dict(zip(signal_cols, model.coef_[0]))
    return coefs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ranked_csv", help="Ranked CSV with a filled-in 'response' column")
    args = parser.parse_args(argv)

    try:
        labeled = load_labeled_rows(args.ranked_csv)
        print(f"{len(labeled)} labeled rows found "
              f"({int(labeled['response'].sum())} positive, {len(labeled) - int(labeled['response'].sum())} negative).")

        if len(labeled) < 30:
            print(
                "Warning: fewer than 30 labeled rows. Coefficients below are highly "
                "noisy -- treat as a rough sanity check only, not a config update.",
                file=sys.stderr,
            )

        coefs = refit(labeled)
    except (ValueError, ImportError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print("\nSuggested weight direction (config key: weight -> [signal_ column]):")
    for signal_col, coef in sorted(coefs.items(), key=lambda kv: -abs(kv[1])):
        config_key = signal_col.removeprefix("signal_")
        if coef > 1e-6:
            flag = ""
        elif coef < -1e-6:
            flag = "  <-- WORKING BACKWARDS: consider dropping or inverting this signal"
        else:
            flag = "  <-- no effect detected (likely no variance in this signal in your data)"
        print(f"  {config_key}: {coef:+.3f}{flag}")

    print(
        "\nThese are raw logistic-regression coefficients, not ready-to-paste "
        "config/scoring.yaml weights. To update the config: keep the *relative* "
        "ordering and rough proportions above, renormalize so your weights sum "
        "to something convenient (e.g. 1.0), and drop or re-examine any signal "
        "flagged as working backwards before trusting it."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
