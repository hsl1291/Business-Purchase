from datetime import datetime

import pandas as pd

from bizbuy.make_call_sheet import build_sheet, why_flagged

NOW = datetime(2026, 9, 28)


def _df():
    return pd.DataFrame({
        "business_name": ["A", "B", "C"],
        "principal_name": ["x", "y", "z"],
        "seller_score": [0.9, 0.8, 0.7],
        "issue_date": ["1990-01-01"] * 3,
        "signal_license_age": [1.0, 1.0, 0.1],
        "signal_single_principal": [1.0, 0.0, 0.0],
        "signal_renewal_lapse": [1.0, 0.0, 0.0],
        "contacted": [None, None, None],
    })


def test_why_flagged_lists_active_signals():
    text = why_flagged(_df().iloc[0], NOW)
    assert "licensed 36 yrs" in text
    assert "single listed principal" in text
    assert "renewal date has passed" in text


def test_why_flagged_fallback_when_nothing_dominant():
    assert "score-only" in why_flagged(_df().iloc[2], NOW)


def test_build_sheet_skips_already_contacted_and_limits_n():
    df = _df()
    df.loc[0, "contacted"] = "2026-09-01"
    sheet = build_sheet(df, n=1, now=NOW)
    assert list(sheet["business_name"]) == ["B"]
    assert {"contact_date", "outcome", "notes"} <= set(sheet.columns)
