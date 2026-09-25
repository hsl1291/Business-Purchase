import pandas as pd

from src.enrich import score_stale_from_place, enrich_real_estate


def test_score_stale_from_place_none_is_neutral():
    assert score_stale_from_place(None) == 0.0


def test_score_stale_from_place_closed_business():
    place = {"businessStatus": "CLOSED_PERMANENTLY", "websiteUri": "https://x.com", "userRatingCount": 50}
    assert score_stale_from_place(place) == 1.0


def test_score_stale_from_place_no_website_no_reviews():
    place = {"userRatingCount": 0}
    assert score_stale_from_place(place) == 1.0


def test_score_stale_from_place_healthy_business():
    place = {"websiteUri": "https://x.com", "userRatingCount": 40, "businessStatus": "OPERATIONAL"}
    assert score_stale_from_place(place) == 0.0


def test_score_stale_from_place_partial_signal():
    # has website but very few reviews -> mild signal, not full
    place = {"websiteUri": "https://x.com", "userRatingCount": 1, "businessStatus": "OPERATIONAL"}
    assert score_stale_from_place(place) == 0.5


def test_enrich_real_estate_no_csv_is_neutral():
    df = pd.DataFrame({"principal_name": ["John Smith"]})
    result = enrich_real_estate(df, None)
    assert (result == 0.0).all()


def test_enrich_real_estate_matches_owner_name(tmp_path):
    assessor_csv = tmp_path / "assessor.csv"
    assessor_csv.write_text("owner_name,property_address\nJohn Smith,123 Main St\n")

    df = pd.DataFrame({"principal_name": ["John Smith", "Jane Doe"]})
    result = enrich_real_estate(df, str(assessor_csv))
    assert result.iloc[0] == 1.0
    assert result.iloc[1] == 0.0


def test_enrich_real_estate_case_and_whitespace_insensitive(tmp_path):
    assessor_csv = tmp_path / "assessor.csv"
    assessor_csv.write_text("owner_name,property_address\n  JOHN SMITH  ,123 Main St\n")

    df = pd.DataFrame({"principal_name": ["john smith"]})
    result = enrich_real_estate(df, str(assessor_csv))
    assert result.iloc[0] == 1.0
