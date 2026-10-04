"""Headless tests of the Streamlit app: every page renders, and the main
flows produce the same numbers as the command line."""
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from bizbuy.gui import APP as _APP  # noqa: E402

APP = str(_APP)
PAGES = ["Home", "Find sellers", "Value a deal", "Compare deals", "Learn from outreach", "Settings & updates"]


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("BIZBUY_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("BIZBUY_NO_UPDATE_CHECK", "1")

    def open_page(name):
        at = AppTest.from_file(APP, default_timeout=60).run()
        at.sidebar.radio[0].set_value(name).run()
        assert not at.exception, at.exception
        return at
    return open_page


@pytest.mark.parametrize("name", PAGES)
def test_every_page_renders(app, name):
    app(name)


def test_find_sellers_scores_sample(app, tmp_path):
    at = app("Find sellers")
    next(b for b in at.button if b.label == "Score businesses").click().run()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Rows read"] == "6"
    table = at.dataframe[0].value
    assert table.iloc[0]["Business"] == "Petrosky & Sons Body Shop"
    assert list((tmp_path / "ws" / "data").glob("ranked_*.csv"))


def test_value_sample_deal_matches_cli_and_saves(app, tmp_path):
    from bizbuy.valuation import evaluate
    import yaml

    at = app("Value a deal")
    at.selectbox[0].set_value("Sample deal").run()
    assert not at.exception
    sample = yaml.safe_load((tmp_path / "ws" / "samples" / "sample_pnl.yaml").read_text())
    expected = evaluate(sample)
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Most an SBA loan can support"] == f"\\${expected['sba_max_supportable_price']:,.0f}"

    next(b for b in at.button if b.label == "Save deal").click().run()
    assert (tmp_path / "ws" / "deals" / "sample_auto_repair_shop.yaml").exists()

    at = app("Compare deals")
    assert at.dataframe[0].value.iloc[0]["Deal"] == "Sample auto repair shop"


def test_compare_with_no_deals_offers_samples(app, tmp_path):
    at = app("Compare deals")
    next(b for b in at.button if b.label == "Load the 3 sample deals").click().run()
    assert len(at.dataframe[0].value) == 3
