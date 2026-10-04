"""BizBuy point-and-click app (Streamlit). Launch with `bizbuy gui`.

Every page is a thin layer over the same functions the command line uses,
so the numbers here always match `bizbuy run` / `bizbuy value` etc.
"""
from __future__ import annotations

import io
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from bizbuy.cli import init_workspace
from bizbuy.deal_tracker import build_comparison
from bizbuy.estimate import estimate, load_benchmarks
from bizbuy.ingest import CANONICAL_FIELDS, REQUIRED_FIELDS, normalize
from bizbuy.make_call_sheet import build_sheet, why_flagged
from bizbuy.score import score
from bizbuy.scorecard import ADJUSTMENTS
from bizbuy.suggest_field_map import sniff_date_format, suggest
from bizbuy.valuation import evaluate

NONE = "(not in this file)"
NOT_ASSESSED = "not assessed"
FIELD_LABELS = {
    "business_name": "Business name",
    "license_number": "License number",
    "license_type": "License type",
    "license_status": "License status",
    "issue_date": "Original issue date",
    "renewal_date": "Expiration / renewal date",
    "principal_name": "Owner / principal",
    "address": "Street address",
    "city": "City",
    "state": "State",
    "zip": "ZIP",
    "naics_code": "NAICS code",
    "employee_count": "Employee count",
}


# ---------------------------------------------------------------- workspace

def workspace() -> Path:
    path = Path(os.environ.get("BIZBUY_WORKSPACE", Path.home() / "BizBuy")).expanduser()
    if not (path / "config" / "scoring.yaml").exists():
        init_workspace(path)
    return path


def load_config(ws: Path) -> dict:
    return yaml.safe_load((ws / "config" / "scoring.yaml").read_text())


def save_config(ws: Path, config: dict) -> None:
    header = "# Saved by the BizBuy app. Edit here or in the app's Settings page.\n"
    (ws / "config" / "scoring.yaml").write_text(header + yaml.safe_dump(config, sort_keys=False))


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "deal"


def money(x) -> str:
    return "—" if x is None or pd.isna(x) else f"${x:,.0f}"


def md(text: str) -> str:
    """Escape $ for Streamlit text, which treats a $...$ pair as a math formula."""
    return text.replace("$", "\\$")


# ---------------------------------------------------------------- pages

def page_home(ws: Path) -> None:
    st.title("BizBuy")
    st.write("Find small businesses likely to sell, and value them once you're talking to the owner.")
    st.markdown(
        """
**How it fits together**

1. **Find sellers**: upload a state license export. Each business gets a
   seller-likelihood score and a rough value range, and you get a call sheet.
2. **Value a deal**: once you have the owner's P&L (after an NDA), get a value
   range, the price an SBA loan can support, and a stress test.
3. **Compare deals**: see every deal you've saved side by side.
4. **Learn from outreach**: after you've logged replies, see which signals
   actually predict a willing seller.
"""
    )
    st.info(
        "The score ranks businesses. It doesn't know who wants to sell. Expect a low "
        "single-digit reply rate on cold outreach, even from the top of the list."
    )
    st.caption(f"Workspace: {ws}")


def page_find_sellers(ws: Path) -> None:
    st.title("Find sellers")
    config = load_config(ws)

    upload = st.file_uploader("License export (CSV)", type=["csv"])
    use_sample = st.checkbox("Use the sample file instead", value=upload is None)
    if upload is not None:
        raw = pd.read_csv(upload, dtype=str)
        source = upload.name
    elif use_sample:
        raw = pd.read_csv(ws / "samples" / "sample_raw_licenses.csv", dtype=str)
        source = "sample_raw_licenses.csv"
    else:
        return

    st.caption(f"{len(raw):,} rows, {len(raw.columns)} columns from {source}")

    st.subheader("1. Match the columns")
    guessed, ambiguous, _ = suggest(list(raw.columns))
    saved = config.get("field_map", {})
    options = [NONE] + list(raw.columns)
    field_map = {}
    all_found = all(f in guessed or saved.get(f) in raw.columns for f in REQUIRED_FIELDS) and not ambiguous
    n_found = sum(1 for f in CANONICAL_FIELDS if f in guessed or saved.get(f) in raw.columns)
    box = st.expander(
        f"Matched {n_found} of {len(CANONICAL_FIELDS)} columns automatically. Click to check or fix.",
        expanded=not all_found,
    )
    cols = box.columns(2)
    for i, field in enumerate(CANONICAL_FIELDS):
        default = saved.get(field) if saved.get(field) in raw.columns else guessed.get(field)
        label = FIELD_LABELS[field] + (" *" if field in REQUIRED_FIELDS else "")
        choice = cols[i % 2].selectbox(
            label, options, index=options.index(default) if default in options else 0,
            key=f"fm_{source}_{field}",
            help="Several columns looked plausible; check this one." if field in ambiguous else None,
        )
        field_map[field] = "" if choice == NONE else choice

    missing = [FIELD_LABELS[f] for f in REQUIRED_FIELDS if not field_map[f]]
    if missing:
        st.error(f"Pick a column for: {', '.join(missing)}")
        return

    sniffed = None
    for f in ("issue_date", "renewal_date"):
        if field_map[f]:
            sniffed = sniff_date_format(raw[field_map[f]])
            if sniffed:
                break
    date_format = box.text_input(
        "Date format", sniffed or config.get("date_format", "%m/%d/%Y"),
        help="%m/%d/%Y = 03/14/1998, %Y-%m-%d = 1998-03-14",
    )

    st.subheader("2. Score")
    remember = st.checkbox("Remember this column matching for next time", value=True)
    if st.button("Score businesses", type="primary"):
        run_config = {**config, "field_map": field_map, "date_format": date_format}
        try:
            normalized = normalize(raw, run_config)
        except ValueError as e:
            st.error(str(e))
            return
        if normalized["issue_date"].isna().all():
            st.error("None of the issue dates could be read. Check the date format above.")
            return
        ranked = score(normalized, run_config)
        result = estimate(ranked, load_benchmarks(str(ws / "config" / "benchmarks.csv")))
        result["contacted"] = ""
        result["response"] = ""
        now = datetime.now()
        result.insert(1, "why_flagged", result.apply(lambda r: why_flagged(r, now), axis=1))

        out = ws / "data" / f"ranked_{datetime.now():%Y%m%d_%H%M}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(out, index=False)
        if remember:
            save_config(ws, run_config)
        st.session_state["ranked"] = result
        st.session_state["ranked_meta"] = (len(normalized), out)

    if "ranked" not in st.session_state:
        return
    result = st.session_state["ranked"]
    n_in, out = st.session_state["ranked_meta"]

    a, b, c = st.columns(3)
    a.metric("Rows read", f"{n_in:,}")
    b.metric("Passed filters", f"{len(result):,}")
    c.metric("Top score", f"{result['seller_score'].max():.2f}" if len(result) else "—")
    if not len(result):
        st.warning("Nothing passed the filters (active status, minimum license age). See Settings.")
        return

    view = pd.DataFrame({
        "Business": result["business_name"],
        "Owner": result["principal_name"],
        "City": result["city"],
        "Score": result["seller_score"].round(2),
        "Why flagged": result["why_flagged"],
        "Rough value (yours only)": result["est_value_low"].map(money) + " – " + result["est_value_high"].map(money),
    })
    st.dataframe(view, hide_index=True, width="stretch")
    st.caption(f"Saved to {out}. The rough value comes from industry averages. Never quote it to a seller.")

    n = st.slider("Call sheet size", 5, max(5, min(200, len(result))), min(25, max(5, len(result))))
    sheet = build_sheet(result, n)
    d1, d2 = st.columns(2)
    d1.download_button("Download call sheet", sheet.to_csv(index=False), "call_sheet.csv", "text/csv")
    d2.download_button("Download full ranked list", result.to_csv(index=False), "ranked.csv", "text/csv")


def deal_form(ws: Path) -> dict:
    """Render the deal inputs and return a deal config dict."""
    deals_dir = ws / "deals"
    existing = sorted(p.stem for p in deals_dir.glob("*.yaml"))
    start = st.selectbox("Start from", ["Blank deal", "Sample deal"] + existing)
    if start == "Sample deal":
        base = yaml.safe_load((ws / "samples" / "sample_pnl.yaml").read_text())
        base.setdefault("deal_name", "Sample auto repair shop")
    elif start == "Blank deal":
        base = {"deal_name": "", "pnl": {"net_profit": 0, "owner_compensation": 0, "add_backs": {}},
                "deal_assumptions": {}, "risk_factors": {}}
    else:
        base = yaml.safe_load((deals_dir / f"{start}.yaml").read_text())
        base.setdefault("deal_name", start)

    pnl, deal, risk = base.get("pnl", {}), base.get("deal_assumptions", {}), base.get("risk_factors") or {}
    k = f"deal_{start}"

    name = st.text_input("Deal name", base.get("deal_name", ""), key=f"{k}_name")

    st.subheader("Financials (from the P&L / tax return)")
    c1, c2 = st.columns(2)
    net_profit = c1.number_input("Net profit", value=float(pnl.get("net_profit", 0)), step=1000.0, key=f"{k}_np", format="%.0f")
    owner_comp = c2.number_input("Owner's salary / draws", value=float(pnl.get("owner_compensation", 0)), step=1000.0, key=f"{k}_oc", format="%.0f")
    st.write("Add-backs (non-cash or one-time costs). Verify every one; this is where sellers inflate.")
    addbacks = pd.DataFrame(
        [{"Item": a, "Amount": float(v)} for a, v in (pnl.get("add_backs") or {}).items()]
        or [{"Item": "depreciation", "Amount": 0.0}]
    )
    addbacks = st.data_editor(addbacks, num_rows="dynamic", width="stretch", key=f"{k}_ab")

    st.subheader("Price and financing")
    c1, c2, c3 = st.columns(3)
    asking = c1.number_input("Asking price (0 = none yet)", value=float(deal.get("asking_price") or 0), step=5000.0, key=f"{k}_ask", format="%.0f")
    m_low = c2.number_input("Multiple, low", value=float(deal.get("multiple_low", 2.0)), step=0.1, key=f"{k}_ml")
    m_high = c3.number_input("Multiple, high", value=float(deal.get("multiple_high", 3.0)), step=0.1, key=f"{k}_mh")
    c1, c2, c3 = st.columns(3)
    reserve = c1.number_input(
        "Your salary from the business", value=float(deal.get("owner_draw_reserve", 0)), step=5000.0, key=f"{k}_res", format="%.0f",
        help="Lenders test loan coverage after paying the owner a market salary. Leaving this at 0 flatters every deal.",
    )
    down = c2.number_input("Down payment %", value=float(deal.get("down_payment_pct", 0.10)) * 100, step=1.0, key=f"{k}_dp", format="%.1f") / 100
    rate = c3.number_input("Interest rate %", value=float(deal.get("annual_rate", 0.115)) * 100, step=0.25, key=f"{k}_rate") / 100
    c1, c2, c3 = st.columns(3)
    term = c1.number_input("Loan term (years)", value=int(deal.get("term_years", 10)), step=1, key=f"{k}_term")
    min_dscr = c2.number_input("Lender's minimum coverage (DSCR)", value=float(deal.get("min_dscr", 1.25)), step=0.05, key=f"{k}_dscr")
    manager = c3.number_input("Market manager salary (optional)", value=float(deal.get("market_manager_salary", 0)), step=5000.0, key=f"{k}_mgr", format="%.0f")

    st.subheader("Risk factors (your diligence)")
    risk_out = {}
    cols = st.columns(2)
    for i, (factor, table) in enumerate(ADJUSTMENTS.items()):
        opts = [NOT_ASSESSED] + list(table)
        cur = risk.get(factor, NOT_ASSESSED)
        pick = cols[i % 2].selectbox(factor.replace("_", " ").capitalize(), opts,
                                     index=opts.index(cur) if cur in opts else 0, key=f"{k}_{factor}")
        if pick != NOT_ASSESSED:
            risk_out[factor] = pick
    c1, c2 = st.columns(2)
    top_cust = c1.number_input("Largest customer's share of revenue % (0 = not assessed)",
                               value=float(risk.get("top_customer_pct", 0)) * 100, step=1.0, key=f"{k}_tc", format="%.1f")
    years = c2.number_input("Years in business (0 = not assessed)", value=float(risk.get("years_in_business", 0)),
                            step=1.0, key=f"{k}_yrs", format="%.0f")
    if top_cust:
        risk_out["top_customer_pct"] = top_cust / 100
    if years:
        risk_out["years_in_business"] = years

    items = {str(r["Item"]).strip(): float(r["Amount"] or 0) for _, r in addbacks.iterrows() if str(r["Item"]).strip()}
    assumptions = {"multiple_low": m_low, "multiple_high": m_high, "down_payment_pct": down,
                   "annual_rate": rate, "term_years": int(term), "min_dscr": min_dscr,
                   "owner_draw_reserve": reserve}
    if asking:
        assumptions["asking_price"] = asking
    if manager:
        assumptions["market_manager_salary"] = manager
    config = {"deal_name": name or "Untitled deal",
              "pnl": {"net_profit": net_profit, "owner_compensation": owner_comp, "add_backs": items},
              "deal_assumptions": assumptions}
    if risk_out:
        config["risk_factors"] = risk_out
    return config


def page_value_deal(ws: Path) -> None:
    st.title("Value a deal")
    form_col, result_col = st.columns([3, 2], gap="large")
    with form_col:
        config = deal_form(ws)
    r = evaluate(config)

    with result_col:
        st.subheader("Result")
        if not config["deal_assumptions"]["owner_draw_reserve"]:
            st.warning("Your salary is set to 0, so the coverage below assumes you work for free.")
        st.metric("SDE (seller's discretionary earnings)", md(money(r["sde"])))
        if r["ebitda_adjusted"] is not None:
            st.metric("Adjusted EBITDA", md(money(r["ebitda_adjusted"])))
        lo, hi = r["sde_multiple_value_range"]
        st.metric("Value range (SDE × multiple)", md(f"{money(lo)} – {money(hi)}"))
        if "risk_adjusted_value" in r:
            st.metric("Risk-adjusted value", md(money(r["risk_adjusted_value"])),
                      help=f"{r['risk_adjusted_multiple']:.2f}× SDE. " + "; ".join(r["risk_adjusted_multiple_notes"]))
        st.metric("Most an SBA loan can support", md(money(r["sba_max_supportable_price"])))

        if "asking_price" in r:
            st.divider()
            ok = r["asking_price_passes_dscr"]
            (st.success if ok else st.error)(md(
                f"At {money(r['asking_price'])}, coverage is {r['asking_price_dscr']:.2f}× "
                f"({'passes' if ok else 'fails'} the {config['deal_assumptions']['min_dscr']:.2f}× minimum)."
            ))
            st.write(md(f"Loan {money(r['asking_price_loan_amount'])}, payments {money(r['asking_price_annual_debt_service'])}/yr"))
            stress = pd.DataFrame({"If SDE is overstated by": list(r["stress_test"]),
                                   "Coverage": [f"{v:.2f}×" for v in r["stress_test"].values()]})
            st.dataframe(stress, hide_index=True, width="stretch")
            if "break_even_sde_haircut" in r:
                be = r["break_even_sde_haircut"]
                st.caption("Already short of the minimum at the claimed SDE." if be < 0 else
                           f"Stops financing if SDE is overstated by more than {be:.0%}.")

        st.divider()
        if st.button("Save deal", type="primary"):
            path = ws / "deals" / f"{slugify(config['deal_name'])}.yaml"
            path.write_text(yaml.safe_dump(config, sort_keys=False))
            st.success(f"Saved to {path}")
        st.caption("Automates the arithmetic, not the judgment. Verify add-backs against tax returns.")


def page_compare(ws: Path) -> None:
    st.title("Compare deals")
    deals_dir = ws / "deals"
    files = sorted(deals_dir.glob("*.yaml"))
    if not files:
        st.info("No saved deals yet. Save one from **Value a deal**, or load the samples.")
        if st.button("Load the 3 sample deals"):
            for p in (ws / "samples" / "deals").glob("*.yaml"):
                (deals_dir / p.name).write_text(p.read_text())
            st.rerun()
        return

    deals = [(yaml.safe_load(p.read_text()) or {}).get("deal_name", p.stem) for p in files]
    table = build_comparison([(n, yaml.safe_load(p.read_text())) for n, p in zip(deals, files)])
    view = pd.DataFrame({
        "Deal": table["deal_name"],
        "SDE": table["sde"].map(money),
        "Value range": table["value_range_low"].map(money) + " – " + table["value_range_high"].map(money),
        "SBA max price": table["sba_max_supportable_price"].map(money),
    })
    if "asking_price" in table:
        view["Asking"] = table["asking_price"].map(money)
        view["Coverage"] = table["asking_price_dscr"].map(lambda v: "—" if pd.isna(v) else f"{v:.2f}×")
        view["Finances?"] = table["passes_dscr"].map(lambda v: "—" if pd.isna(v) else ("Yes" if v else "No"))
        view["Room vs max price"] = table["headroom_vs_max_price"].map(money)
    st.dataframe(view, hide_index=True, width="stretch")
    st.download_button("Download comparison", table.to_csv(index=False), "deal_comparison.csv", "text/csv")
    st.caption(f"Deals are YAML files in {deals_dir}")


def page_learn(ws: Path) -> None:
    st.title("Learn from outreach")
    st.write(
        "Open a ranked list from **Find sellers** in Excel. Fill in **response** with 1 for an "
        "interested reply and 0 for no reply or a no. Leave it blank for anyone you haven't contacted. "
        "Then upload it here."
    )
    upload = st.file_uploader("Ranked list with responses (CSV)", type=["csv"])
    if upload is None:
        return
    from bizbuy.refit_weights import load_labeled_rows, refit

    try:
        labeled = load_labeled_rows(io.BytesIO(upload.getvalue()))
        coefs = refit(labeled)
    except (ValueError, ImportError) as e:
        st.error(str(e))
        return
    pos = int(labeled["response"].sum())
    st.write(f"{len(labeled)} logged responses ({pos} positive).")
    if len(labeled) < 30:
        st.warning("Under 30 responses: treat this as a rough hint, not a reason to change weights.")

    def verdict(c):
        return "Predicts replies" if c > 1e-6 else ("Working backwards" if c < -1e-6 else "No effect seen yet")

    st.dataframe(pd.DataFrame({
        "Signal": [k.removeprefix("signal_").replace("_", " ") for k in coefs],
        "Strength": [round(v, 3) for v in coefs.values()],
        "Verdict": [verdict(v) for v in coefs.values()],
    }).sort_values("Strength", ascending=False), hide_index=True, width="stretch")
    st.caption("Adjust the weights on the Settings page if this holds up over more data.")


def page_settings(ws: Path) -> None:
    from bizbuy.update import UpdateError, current_version, is_git_install, update_git_install

    st.title("Settings & updates")

    st.subheader("Updates")
    st.write(f"Installed version: **{current_version()}**")
    app_settings_path = ws / "config" / "app.yaml"
    try:
        app_settings = yaml.safe_load(app_settings_path.read_text()) or {}
    except OSError:
        app_settings = {}
    auto = st.toggle(
        "Update automatically from GitHub each time BizBuy opens",
        value=bool(app_settings.get("auto_update", True)),
        help="BizBuy checks GitHub when it starts and installs anything new before opening. "
             "If GitHub can't be reached, it opens the version you have.",
    )
    if auto != bool(app_settings.get("auto_update", True)):
        app_settings["auto_update"] = auto
        app_settings_path.write_text(yaml.safe_dump(app_settings))
        st.success("Saved.")
    if not is_git_install():
        st.info("This copy wasn't installed with the installer, so it can't update itself from here.")
    else:
        c1, c2 = st.columns(2)
        if c1.button("Check for updates"):
            try:
                st.info(update_git_install(check_only=True))
            except UpdateError as e:
                st.error(str(e))
        if c2.button("Update now", type="primary"):
            with st.spinner("Pulling the latest version..."):
                try:
                    msg = update_git_install()
                    updates_behind.clear()
                    st.success(msg)
                    if "Updated" in msg:
                        st.warning("Close this window and the BizBuy console, then reopen BizBuy to use the new version.")
                    elif "Switched" in msg:
                        st.warning("Close and reopen BizBuy to use it.")
                except UpdateError as e:
                    st.error(str(e))
                except subprocess.CalledProcessError:
                    st.error("The code updated, but installing new dependencies failed (Windows can lock "
                             "files while the app is open). Close BizBuy and run the installer again; "
                             "your data is safe.")

    st.subheader("Seller-score weights")
    config = load_config(ws)
    st.write("These say how much each signal counts. Only their relative sizes matter.")
    weights = {}
    cols = st.columns(3)
    for i, (name, w) in enumerate(config["weights"].items()):
        weights[name] = cols[i % 3].number_input(name.replace("_", " ").capitalize(), value=float(w),
                                                 min_value=0.0, step=0.05, key=f"w_{name}")
    f = config.get("filters", {})
    min_age = st.number_input("Skip businesses licensed fewer than N years ago",
                              value=int(f.get("min_license_age_years", 5)), min_value=0, step=1)
    if st.button("Save settings"):
        config["weights"] = weights
        config.setdefault("filters", {})["min_license_age_years"] = int(min_age)
        save_config(ws, config)
        st.success("Saved.")

    st.subheader("Google Places (optional)")
    st.write("Used by `bizbuy enrich` to check whether a business has a website or recent reviews. "
             "Set the GOOGLE_PLACES_API_KEY environment variable to enable it.")
    st.caption(f"Workspace folder: {ws}")


PAGES = {
    "Home": page_home,
    "Find sellers": page_find_sellers,
    "Value a deal": page_value_deal,
    "Compare deals": page_compare,
    "Learn from outreach": page_learn,
    "Settings & updates": page_settings,
}


@st.cache_data(ttl=3600, show_spinner=False)
def updates_behind() -> int | None:
    from bizbuy.update import updates_available_quietly
    return updates_available_quietly()


def main() -> None:
    st.set_page_config(page_title="BizBuy", layout="wide")
    ws = workspace()
    choice = st.sidebar.radio("BizBuy", list(PAGES), label_visibility="collapsed")
    if os.environ.get("BIZBUY_NO_UPDATE_CHECK") != "1":
        behind = updates_behind()
        if behind:
            st.sidebar.info(f"An update is available ({behind} change{'s' if behind > 1 else ''}). "
                            "Install it from **Settings & updates**.")
    PAGES[choice](ws)


main()
