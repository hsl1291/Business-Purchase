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

1. On GitHub, click **Code → Download ZIP**, and unzip it anywhere (for
   example, Downloads).
2. Double-click the installer in the unzipped folder:
   - **Windows:** `Install BizBuy.cmd`. If Windows shows "Windows protected
     your PC", click **More info → Run anyway**.
   - **Mac:** `Install BizBuy.command`. If macOS says it can't be opened,
     right-click it and choose **Open**.
3. Answer its questions. If Python or Git is missing, it offers to install it
   (via winget on Windows, Homebrew on a Mac). The first time it downloads the
   app, sign in to GitHub when asked.

When it finishes, BizBuy opens in your browser. Afterwards, open it from the
**BizBuy** shortcut on your Desktop (Windows: also the Start menu). A small
console window opens with it; that window *is* the app, so leave it open while
you work and close it to quit.

The installer keeps everything in `~/.bizbuy` (Windows:
`%USERPROFILE%\.bizbuy`) and your data in `~/BizBuy`. Nothing is installed
system-wide besides Python and Git. You can run it again any time; it updates
in place.

Prefer a terminal? Run `powershell -ExecutionPolicy Bypass -File install.ps1`
(Windows) or `bash install.sh` (Mac/Linux).

## Updates are automatic

You install once. After that, **every time you open BizBuy it checks GitHub
and installs anything new before the app opens**. There's nothing to
download and nothing to reinstall. You'll see "Checking GitHub for updates..."
in the console window, and "Updated to the latest version" when there was
something new.

- If GitHub can't be reached (offline, or not signed in), BizBuy opens the
  version you already have and tries again next time.
- Installs follow the repo's **default branch** on GitHub. If that changes
  (say a branch is merged into `main` and deleted), installs switch over on
  their own.
- To update mid-session, use **Settings & updates → Update now**, then close and
  reopen BizBuy. You can turn automatic updates off on the same page.
- Your data folder (`~/BizBuy`) is never touched by an update. An update is
  skipped if someone edited code inside the install folder, so those edits
  aren't overwritten.

From a terminal: `bizbuy update --check`, `bizbuy update`, `bizbuy version`.
Re-running the installer is only needed if an update fails partway through
(it repairs in place).

## The app

| Page | What it does |
|---|---|
| Find sellers | Upload a license export (CSV). It matches the columns for you, scores every business, explains why each was flagged, and gives you a call sheet to download |
| Value a deal | Enter the P&L, add-backs, price and risk factors. You get the value range, the most an SBA loan can support, the loan coverage at the asking price, and a stress test. Save deals for later |
| Compare deals | Every saved deal side by side |
| Learn from outreach | Upload a ranked list with replies filled in to see which signals actually predict a willing seller |
| Settings & updates | Score weights, filters, and the update button |

## Command line

Everything in the app is also available as a command.


```bash
bizbuy gui                    # the point-and-click app
bizbuy init ~/BizBuy          # workspace: editable config + sample data (the app does this for you)
cd ~/BizBuy
bizbuy run samples/sample_raw_licenses.csv
```

A workspace contains the following:

| Folder (`~/BizBuy`) | What goes there |
|---|---|
| `config/scoring.yaml` | Signal weights, filters, and the column mapping for your license export |
| `config/benchmarks.csv` | NAICS benchmarks: revenue/employee, SDE margin, multiple range |
| `data/raw/` | Your license-board / Secretary-of-State exports |
| `deals/` | One P&L YAML per deal you're evaluating |
| `samples/` | Example inputs (a sample P&L, sample licenses, sample deals) |

Commands use `./config/…` when you run them inside a workspace. Anywhere else,
they fall back to the bundled defaults.

### Commands

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
