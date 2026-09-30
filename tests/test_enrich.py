import pandas as pd

from bizbuy.enrich import score_stale_from_place, enrich_real_estate


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


def test_enrich_web_presence_uses_cache_and_skips_api(tmp_path, monkeypatch):
    import json

    from bizbuy import enrich

    cache_file = tmp_path / "cache.json"
    cache_file.write_text(json.dumps({
        "joe's shop|springfield|il": {"websiteUri": "https://x.com", "userRatingCount": 30, "businessStatus": "OPERATIONAL"}
    }))

    def boom(*a, **k):
        raise AssertionError("API should not be called on a cache hit")

    monkeypatch.setattr(enrich, "places_lookup", boom)
    df = pd.DataFrame({"business_name": ["Joe's Shop"], "city": ["Springfield"], "state": ["IL"]})
    result = enrich.enrich_web_presence(df, "key", rate_limit_sec=0, cache_path=str(cache_file))
    assert result.iloc[0] == 0.0


def test_enrich_web_presence_does_not_cache_failed_lookups(tmp_path, monkeypatch):
    from bizbuy import enrich

    cache_file = tmp_path / "cache.json"
    monkeypatch.setattr(enrich, "places_lookup", lambda *a, **k: None)
    df = pd.DataFrame({"business_name": ["Ghost"], "city": ["X"], "state": ["IL"]})
    enrich.enrich_web_presence(df, "key", rate_limit_sec=0, cache_path=str(cache_file))
    assert not cache_file.exists() or "ghost|x|il" not in cache_file.read_text()
