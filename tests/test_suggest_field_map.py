import pandas as pd

from bizbuy.suggest_field_map import sniff_date_format, suggest


def test_suggest_maps_typical_headers():
    cols = ["Licensee Name", "License No.", "License Status", "Original Issue Date",
            "Expiration Date", "City", "State", "Zip Code", "Street Address"]
    fm, _, unmatched = suggest(cols)
    assert fm["license_number"] == "License No."
    assert fm["license_status"] == "License Status"
    assert fm["issue_date"] == "Original Issue Date"
    assert fm["renewal_date"] == "Expiration Date"
    assert fm["city"] == "City"
    assert fm["zip"] == "Zip Code"
    assert unmatched == []


def test_status_column_not_stolen_by_state():
    fm, _, _ = suggest(["Status", "State"])
    assert fm["license_status"] == "Status"
    assert fm["state"] == "State"


def test_unmatched_columns_reported():
    _, _, unmatched = suggest(["Business Name", "Favorite Color"])
    assert unmatched == ["Favorite Color"]


def test_sniff_date_format():
    assert sniff_date_format(pd.Series(["03/14/1998", "11/30/2026"])) == "%m/%d/%Y"
    assert sniff_date_format(pd.Series(["1998-03-14", "2026-11-30"])) == "%Y-%m-%d"
    assert sniff_date_format(pd.Series(["garbage", "more garbage"])) is None
