"""One-command pipeline: raw license CSV -> normalized -> scored -> estimated.

Chains src.ingest, src.score, and src.estimate so you don't have to run each
step by hand. Enrichment (src.enrich) is a separate, optional step you run
in between if you want it -- see README.md.

Usage:
    python run.py data/raw/state_licenses.csv --config config/scoring.yaml \
        --benchmarks data/benchmarks.csv --out-dir data/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

from src.ingest import normalize
from src.score import score as score_fn
from src.estimate import estimate as estimate_fn, load_benchmarks


def run_pipeline(raw_csv: str, config_path: str, benchmarks_path: str, out_dir: str) -> Path:
    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    print(f"[1/3] Ingesting {raw_csv} ...")
    raw_df = pd.read_csv(raw_csv, dtype=str)
    normalized = normalize(raw_df, config)
    normalized_path = out_dir_path / "normalized.csv"
    normalized.to_csv(normalized_path, index=False)
    print(f"      {len(normalized)} rows -> {normalized_path}")

    print("[2/3] Scoring ...")
    ranked = score_fn(normalized, config)
    ranked_path = out_dir_path / "ranked.csv"
    ranked.to_csv(ranked_path, index=False)
    n_dropped = len(normalized) - len(ranked)
    print(f"      {len(ranked)} rows scored ({n_dropped} filtered out) -> {ranked_path}")

    print("[3/3] Estimating rough value ranges ...")
    benchmarks = load_benchmarks(benchmarks_path)
    final = estimate_fn(ranked, benchmarks)
    # outreach-tracking columns: blank until you fill them in as you contact people
    final["contacted"] = ""
    final["response"] = ""
    final_path = out_dir_path / "ranked_with_estimate.csv"
    final.to_csv(final_path, index=False)
    print(f"      -> {final_path}")

    print()
    print(f"Done. Top candidate: {final.iloc[0]['business_name']} "
          f"(score {final.iloc[0]['seller_score']:.3f})" if len(final) else "Done. No rows survived filtering.")
    print(f"Fill in 'contacted'/'response' in {final_path} as you do outreach, "
          f"then run tools/refit_weights.py once you have ~50+ responses logged.")

    return final_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_csv", help="Path to the raw license/SOS export CSV")
    parser.add_argument("--config", default="config/scoring.yaml")
    parser.add_argument("--benchmarks", default="data/benchmarks.csv")
    parser.add_argument("--out-dir", default="data")
    args = parser.parse_args(argv)

    run_pipeline(args.raw_csv, args.config, args.benchmarks, args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
