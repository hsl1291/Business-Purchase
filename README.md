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
| `src/enrich.py` | Populates `stale_web_presence` (real, via Google Places API) and `owns_real_estate` (manual county-assessor CSV join) |
| `src/deal_tracker.py` | Compares multiple candidate deals side by side, sorted by financing headroom |
| `run.py` | One-command pipeline: raw CSV → ingest → score → estimate |
| `tools/refit_weights.py` | Refits `score.py`'s signal weights from logged outreach outcomes |
| `tests/` | Unit tests for the scoring and valuation math |

## Quickstart

```bash
pip install -r requirements.txt

# All-in-one: ingest -> score -> rough estimate, in one command
python run.py data/sample_raw_licenses.csv --config config/scoring.yaml \
    --benchmarks data/benchmarks.csv --out-dir data/

# ...or run each step by hand:
python -m src.ingest data/raw/state_licenses.csv --config config/scoring.yaml -o data/normalized.csv
python -m src.score data/normalized.csv --config config/scoring.yaml -o data/ranked.csv
python -m src.estimate data/ranked.csv --benchmarks data/benchmarks.csv -o data/ranked_with_estimate.csv

# Optional: enrich with real web-presence signal (needs GOOGLE_PLACES_API_KEY)
# and/or a manually-exported county assessor CSV, then re-score
python -m src.enrich data/ranked.csv -o data/ranked_enriched.csv --assessor-csv data/assessor_export.csv
python -m src.score data/ranked_enriched.csv --config config/scoring.yaml -o data/ranked.csv

# Post-NDA valuation once you have a P&L (see data/sample_pnl.yaml for the format)
python -m src.valuation data/sample_pnl.yaml

# Compare several live deals side by side (one YAML per deal, same format as above)
python -m src.deal_tracker data/deals/ -o data/deal_comparison.csv
```

## Closing the loop: outreach tracking and weight refitting

`run.py` adds blank `contacted` / `response` columns to its output CSV. As you
call or email businesses on the list, fill in:
- `contacted`: date you reached out
- `response`: `1` if they gave a positive/interested reply, `0` if not (leave
  blank if you haven't heard back yet or haven't contacted them)

Once you have on the order of 50+ logged responses, run:

```bash
python tools/refit_weights.py data/ranked_with_estimate.csv
```

This fits a logistic regression of response on the signal columns and prints
which signals are actually predictive -- and flags any that are working
backwards. It won't rewrite `config/scoring.yaml` for you; review the
suggested direction against your own judgment before updating the weights.

## Important caveats

- **The score ranks, it doesn't predict.** Treat the top of the list as "call
  these first," not "these are for sale." Expect a low single-digit percent
  response rate on cold outreach even from a well-targeted list.
- **The weights in `config/scoring.yaml` are starting guesses.** `run.py`
  already adds `contacted`/`response` columns to its output; fill them in as
  you do outreach, then run `tools/refit_weights.py` once you have a few
  hundred data points (it'll work, noisily, from as few as 30-50).
- **`owns_real_estate` needs a manual county assessor export.** There's no
  nationwide API for property records, so `src/enrich.py` documents the
  workflow (search/export by owner name on your county's assessor site) but
  doesn't call anything for you.
- **The pre-contact estimate (`src/estimate.py`) is a rough range, not a
  valuation.** It's built from industry averages, not the business's actual
  numbers. Never quote it to a seller — use it only to prioritize your list.
- **The post-NDA valuation (`src/valuation.py`) automates arithmetic, not
  judgment.** It will not tell you whether an add-back is legitimate, whether
  the tax returns match the books, or whether the owner is core to customer
  relationships. That's still a human diligence question — bring in a
  quality-of-earnings review for anything above Main Street size.
