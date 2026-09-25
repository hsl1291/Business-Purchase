import pandas as pd
import pytest

from src.ingest import normalize


CONFIG = {
    "field_map": {
        "business_name": "Business Name",
        "license_status": "Status",
        "issue_date": "Original Issue Date",
        "renewal_date": "Expiration Date",
        "principal_name": "Owner Name",
        "naics_code": "NAICS",
        "employee_count": "",
    },
    "date_format": "%m/%d/%Y",
}


def test_normalize_maps_columns_and_parses_dates():
    raw = pd.DataFrame(
        {
            "Business Name": ["Joe's Shop"],
            "Status": ["Active"],
            "Original Issue Date": ["03/14/1998"],
            "Expiration Date": ["11/30/2026"],
            "Owner Name": ["Joe Smith"],
            "NAICS": ["811111"],
        }
    )
    result = normalize(raw, CONFIG)
    assert result.iloc[0]["business_name"] == "Joe's Shop"
    assert result.iloc[0]["issue_date"] == pd.Timestamp("1998-03-14")
    assert pd.isna(result.iloc[0]["employee_count"])


def test_normalize_raises_on_missing_required_column():
    raw = pd.DataFrame({"Business Name": ["Joe's Shop"]})  # missing Status, dates
    with pytest.raises(ValueError):
        normalize(raw, CONFIG)
