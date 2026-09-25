from datetime import datetime

import pandas as pd

from src.score import (
    score_license_age,
    score_single_principal,
    score_renewal_lapse,
    score_size_band_fit,
    apply_filters,
    score,
)


NOW = datetime(2026, 1, 1)

CONFIG = {
    "filters": {
        "license_status_include": ["Active"],
        "min_license_age_years": 5,
        "exclude_business_name_contains": [],
    },
    "weights": {
        "license_age": 0.5,
        "single_principal": 0.3,
        "size_band_fit": 0.2,
    },
    "license_age": {"max_years": 30},
    "renewal_lapse": {"lapse_penalty_score": 1.0, "on_time_score": 0.0},
    "size_band_fit": {"min_employees": 5, "max_employees": 50},
}


def make_df():
    return pd.DataFrame(
        {
            "business_name": ["Old Solo Shop", "New Family Biz", "Inactive Old Shop"],
            "license_status": ["Active", "Active", "Inactive"],
            "issue_date": [
                pd.Timestamp("1998-01-01"),
                pd.Timestamp("2023-01-01"),
                pd.Timestamp("1990-01-01"),
            ],
            "renewal_date": [
                pd.Timestamp("2026-06-01"),
                pd.Timestamp("2026-06-01"),
                pd.Timestamp("2026-06-01"),
            ],
            "principal_name": ["John Smith", "Bob and Carol Jones", "Sam Lee"],
            "employee_count": [10, 8, 15],
        }
    )


def test_score_license_age_old_business_scores_high():
    df = make_df()
    result = score_license_age(df, CONFIG, NOW)
    # ~28 years old / 30 year cap -> close to 1.0
    assert result.iloc[0] > 0.9
    # ~3 years old -> close to 0.1
    assert result.iloc[1] < 0.15


def test_score_single_principal_detects_multiple_names():
    df = make_df()
    result = score_single_principal(df)
    assert result.iloc[0] == 1.0  # "John Smith"
    assert result.iloc[1] == 0.0  # "Bob and Carol Jones"


def test_score_size_band_fit():
    df = make_df()
    result = score_size_band_fit(df, CONFIG)
    assert (result == 1.0).all()  # all within 5-50 band


def test_apply_filters_drops_inactive_and_too_new():
    df = make_df()
    filtered = apply_filters(df, CONFIG, NOW)
    # "New Family Biz" is too new (3 yrs < 5 yr minimum); "Inactive Old Shop"
    # is filtered by status
    assert list(filtered["business_name"]) == ["Old Solo Shop"]


def test_score_ranks_old_solo_business_highest():
    df = make_df()
    ranked = score(df, CONFIG, NOW)
    assert len(ranked) == 1
    assert ranked.iloc[0]["business_name"] == "Old Solo Shop"
    assert 0.0 <= ranked.iloc[0]["seller_score"] <= 1.0


def test_score_handles_missing_optional_signals_without_error():
    # single_principal/size_band_fit present, but no enrichment columns
    # (stale_web_presence, owns_real_estate) -- should not raise.
    df = make_df()
    config = dict(CONFIG)
    config["weights"] = {**CONFIG["weights"], "stale_web_presence": 0.1, "owns_real_estate": 0.1}
    ranked = score(df, config, NOW)
    assert "signal_stale_web_presence" in ranked.columns
    assert (ranked["signal_stale_web_presence"] == 0.0).all()
