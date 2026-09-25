# Business Purchase Toolkit

Tools for finding small businesses that are good acquisition candidates, and for
valuing them once you're in conversation with the owner.

This is **not** a lead-generation service and it does not know who "wants to
sell." It ranks businesses by public signals correlated with a higher chance of
an eventual sale (owner age proxies, succession risk, disengagement signals),
and it automates the arithmetic of small-business valuation once you have real
financials. Judgment — verifying add-backs, reading the owner, assessing
industry risk — is still yours.

## What's here

| Path | Purpose |
|---|---|
| `config/scoring.yaml` | Signal weights, hard filters, and the field-name mapping for whatever state/license export you're using |
| `data/raw/` | Drop raw license-board / Secretary-of-State CSV exports here (gitignored) |
| `data/benchmarks.csv` | NAICS-code benchmarks: revenue/employee, typical SDE margin, typical multiple range |
| `src/ingest.py` | Normalizes a raw license CSV into a common schema |
| `src/score.py` | Computes the seller-likelihood score and writes a ranked CSV |
| `src/estimate.py` | Pre-contact rough valuation range from employee count + NAICS benchmarks |
| `src/valuation.py` | Post-NDA valuation: SDE/EBITDA recast, multiple bands, SBA loan sizing, max supportable price |
| `tests/` | Unit tests for the scoring and valuation math |

## Quickstart

```bash
pip install -r requirements.txt

# 1. Normalize a raw license export into the common schema
python -m src.ingest data/raw/state_licenses.csv --config config/scoring.yaml -o data/normalized.csv

# 2. Score and rank
python -m src.score data/normalized.csv --config config/scoring.yaml -o data/ranked.csv

# 3. Rough pre-contact valuation range (no financials, just NAICS + employee count)
python -m src.estimate data/ranked.csv --benchmarks data/benchmarks.csv -o data/ranked_with_estimate.csv

# 4. Post-NDA valuation once you have a P&L (see data/sample_pnl.yaml for the format)
python -m src.valuation data/sample_pnl.yaml
```

## Important caveats

- **The score ranks, it doesn't predict.** Treat the top of the list as "call
  these first," not "these are for sale." Expect a low single-digit percent
  response rate on cold outreach even from a well-targeted list.
- **The weights in `config/scoring.yaml` are starting guesses.** Add a
  `contacted` / `response` column to your ranked CSV as you do outreach, and
  refit the weights (see `tests/test_score.py` for the scoring function you'd
  feed a logistic regression) once you have a few hundred data points.
- **The pre-contact estimate (`src/estimate.py`) is a rough range, not a
  valuation.** It's built from industry averages, not the business's actual
  numbers. Never quote it to a seller — use it only to prioritize your list.
- **The post-NDA valuation (`src/valuation.py`) automates arithmetic, not
  judgment.** It will not tell you whether an add-back is legitimate, whether
  the tax returns match the books, or whether the owner is core to customer
  relationships. That's still a human diligence question — bring in a
  quality-of-earnings review for anything above Main Street size.
