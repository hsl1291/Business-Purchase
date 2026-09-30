# Business Purchase Toolkit

Tools for finding small businesses that are good acquisition candidates, and for
valuing them once you're in conversation with the owner.

This is **not** a lead-generation service and it does not know who "wants to
sell." It ranks businesses by public signals correlated with a higher chance of
an eventual sale (owner age proxies, succession risk, disengagement signals),
and it automates the arithmetic of small-business valuation once you have real
financials. Judgment — verifying add-backs, reading the owner, assessing
industry risk — is still yours.

## Install

You need **Python 3.10+** and **git**. The installer clones this repo into
`~/.bizbuy/app` (Windows: `%USERPROFILE%\.bizbuy\app`), creates a private
Python environment next to it, and puts a `bizbuy` command on your PATH.
Nothing is installed system-wide.

**Windows** (PowerShell): download `install.ps1` from this repo, then

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

Open a new terminal afterwards so the PATH change takes effect.

**macOS / Linux:**

```bash
curl -fsSL https://raw.githubusercontent.com/hsl1291/Business-Purchase/HEAD/install.sh | bash
```

If the repo is private, the `curl` link won't work. Instead, download
`install.sh` while signed in to GitHub, run `bash install.sh`, and sign in when
git asks.

## Update

```bash
bizbuy update --check   # see whether anything new is available
bizbuy update           # pull it
bizbuy version          # branch, commit and date you're on
```

`bizbuy update` runs `git pull` on the install. Dependencies are reinstalled only
when `requirements.txt` changed. Your workspace is never touched, because it lives
in a separate folder. The update refuses to run if someone edited code inside the
install folder, so those edits can't be silently overwritten. If an update ever
adds a new command that doesn't show up, re-run the installer. That's safe, and it
updates in place.

## Get started

```bash
bizbuy init ~/BizBuy          # workspace: editable config + sample data
cd ~/BizBuy
bizbuy run samples/sample_raw_licenses.csv
```

A workspace contains the following:

| Folder | What goes there |
|---|---|
| `config/scoring.yaml` | Signal weights, filters, and the column mapping for your license export |
| `config/benchmarks.csv` | NAICS benchmarks: revenue/employee, SDE margin, multiple range |
| `data/raw/` | Your license-board / Secretary-of-State exports |
| `deals/` | One P&L YAML per deal you're evaluating |
| `samples/` | Example inputs (a sample P&L, sample licenses, sample deals) |

Commands use `./config/…` when you run them inside a workspace. Anywhere else,
they fall back to the bundled defaults.

## Commands

```bash
# New license export: draft the column mapping, paste it into config/scoring.yaml
bizbuy fieldmap data/raw/your_export.csv

# Ingest -> score -> rough value estimate, in one step
bizbuy run data/raw/your_export.csv

# Optional enrichment (Google Places needs GOOGLE_PLACES_API_KEY; the
# assessor CSV is a manual export from your county's site), then re-score
bizbuy enrich data/ranked.csv -o data/ranked_enriched.csv --assessor-csv data/assessor.csv
bizbuy score data/ranked_enriched.csv -o data/ranked.csv

# Outreach sheet: top 25 uncontacted, each with the reason it was flagged
bizbuy callsheet data/ranked_with_estimate.csv -n 25 -o data/call_sheet.csv

# After an NDA: value one deal (format: samples/sample_pnl.yaml)
bizbuy value deals/some_shop.yaml

# Compare every deal in a folder side by side
bizbuy deals deals/ -o data/deal_comparison.csv

# Once outreach results are logged: which signals actually predict replies?
bizbuy refit data/ranked_with_estimate.csv
```

`bizbuy <command> -h` shows the options for any command. The individual pipeline
steps are also available as `bizbuy ingest`, `bizbuy score` and `bizbuy estimate`.

## Closing the loop: outreach tracking and weight refitting

`bizbuy run` adds blank `contacted` / `response` columns to its output CSV. As
you contact businesses on the list, fill in:
- `contacted`: the date you reached out
- `response`: `1` for a positive or interested reply, `0` if not. Leave it
  blank if you haven't heard back yet.

Once you have 50 or more logged responses, run `bizbuy refit`. It shows which
signals actually predict replies and flags any that work backwards. It won't
rewrite your config. Review its output, then adjust the weights yourself.

## Development

```bash
git clone https://github.com/hsl1291/Business-Purchase.git && cd Business-Purchase
make install   # editable install with test deps
make test
make demo      # full pipeline on sample data in ./demo-workspace
```

Code lives in `bizbuy/`, bundled defaults in `bizbuy/resources/`, and the command
dispatcher in `bizbuy/cli.py`. The self-update logic is in `bizbuy/update.py`.

## Important caveats

- **The score ranks, it doesn't predict.** Treat the top of the list as "call
  these first," not "these are for sale." Expect a low single-digit percent
  response rate on cold outreach even from a well-targeted list.
- **The weights in `config/scoring.yaml` are starting guesses.** Refit them
  with `bizbuy refit` once you have a few hundred logged responses. It will
  run, noisily, from as few as 30-50.
- **`owns_real_estate` needs a manual county assessor export.** There's no
  nationwide API for property records, so `bizbuy enrich` documents the
  workflow (search/export by owner name on your county's assessor site) but
  doesn't call anything for you.
- **The pre-contact estimate (`bizbuy run` / `bizbuy estimate`) is a rough range, not a
  valuation.** It's built from industry averages, not the business's actual
  numbers. Never quote it to a seller — use it only to prioritize your list.
- **Set `owner_draw_reserve` honestly.** SDE includes the owner's pay. If the
  reserve is 0, DSCR assumes you'll work for free and every deal looks
  better than a lender will see it. `bizbuy value` warns when it's 0. The
  stress test shows how much SDE overstatement a deal can absorb before it
  stops financing; sellers inflate add-backs, so lean on it.
- **The scorecard (the `risk_factors` block in a deal file) is only as good as your inputs.** Its
  adjustments are conventions, not market data. Tune them to your deals.
- **The post-NDA valuation (`bizbuy value`) automates arithmetic, not
  judgment.** It will not tell you whether an add-back is legitimate, whether
  the tax returns match the books, or whether the owner is core to customer
  relationships. That's still a human diligence question — bring in a
  quality-of-earnings review for anything above Main Street size.
